"""Complex Financial Structure Analysis Engine.

Analyzes the parts of a company's structure that simple ratio analysis
misses, and that make a business "complex":

  1. Corporate/subsidiary org tree (holding-company depth, offshore mix)
  2. Multi-class equity (voting vs economic control "wedge", dual-class)
  3. Off-balance-sheet & VIE exposure (operating leases, guarantees, SPEs)
  4. Debt subordination waterfall (seniority, secured vs unsecured,
     structural subordination across opco/holdco)

Pure computation — no DB/network. Inputs are plain dicts/lists (sourced from
EDGAR EX-21 subsidiary exhibits, XBRL share-class facts, the platform's
capital-structure tranches, and balance-sheet line items). Builds on the
existing capital-structure data without duplicating it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Jurisdictions commonly used for tax/structuring purposes — a high share of
# subsidiaries here flags structural opacity (not wrongdoing).
TAX_ADVANTAGED_JURISDICTIONS: set[str] = {
    "CAYMAN ISLANDS", "BERMUDA", "BRITISH VIRGIN ISLANDS", "LUXEMBOURG",
    "IRELAND", "NETHERLANDS", "JERSEY", "GUERNSEY", "ISLE OF MAN",
    "MAURITIUS", "PANAMA", "BAHAMAS", "MARSHALL ISLANDS", "SINGAPORE",
    "HONG KONG", "SWITZERLAND", "MALTA", "CYPRUS", "GIBRALTAR", "DELAWARE",
}


# ── 1. Subsidiary / holding-company tree ────────────────────────────────

def analyze_subsidiary_tree(subsidiaries: list[dict], parent_name: str | None = None) -> dict:
    """Summarize a corporate subsidiary structure.

    Each subsidiary dict: name, jurisdiction, ownership_pct (optional),
    parent (optional, for depth), is_vie (optional bool).
    """
    total = len(subsidiaries)
    by_jurisdiction: dict[str, int] = {}
    offshore = 0
    vie_count = 0
    minority_owned = 0

    for sub in subsidiaries:
        jur = (sub.get("jurisdiction") or "UNKNOWN").strip().upper()
        by_jurisdiction[jur] = by_jurisdiction.get(jur, 0) + 1
        if jur in TAX_ADVANTAGED_JURISDICTIONS:
            offshore += 1
        if sub.get("is_vie"):
            vie_count += 1
        pct = sub.get("ownership_pct")
        if pct is not None and pct < 100:
            minority_owned += 1

    offshore_pct = round(offshore / total * 100, 1) if total else 0.0

    # Tree depth from explicit parent links (1 = flat under the registrant).
    depth = _tree_depth(subsidiaries, parent_name)

    return {
        "total_subsidiaries": total,
        "distinct_jurisdictions": len(by_jurisdiction),
        "jurisdiction_breakdown": dict(sorted(by_jurisdiction.items(), key=lambda kv: kv[1], reverse=True)),
        "offshore_count": offshore,
        "offshore_pct": offshore_pct,
        "vie_count": vie_count,
        "minority_owned_count": minority_owned,
        "max_depth": depth,
        "complexity_flag": offshore_pct > 30 or len(by_jurisdiction) > 15 or depth >= 4,
    }


def _tree_depth(subsidiaries: list[dict], root: str | None) -> int:
    """Compute max depth of the parent→child graph; 1 if flat/unknown."""
    children: dict[str, list[str]] = {}
    for sub in subsidiaries:
        parent = (sub.get("parent") or root or "__ROOT__")
        children.setdefault(parent, []).append(sub.get("name", ""))
    if not children:
        return 0

    def _depth(node: str, seen: set[str]) -> int:
        if node in seen:
            return 0
        seen = seen | {node}
        kids = children.get(node, [])
        if not kids:
            return 1
        return 1 + max((_depth(k, seen) for k in kids), default=0)

    start = root or "__ROOT__"
    return max(_depth(start, set()) - 1, 1) if (root or "__ROOT__") in children else 1


# ── 2. Multi-class equity (control wedge) ───────────────────────────────

def analyze_share_classes(classes: list[dict]) -> dict:
    """Analyze multi-class share structures for voting vs economic divergence.

    Each class dict: class_name, shares_outstanding, votes_per_share
    (default 1), economic_rights (default 1.0 = pari passu dividend rights).
    """
    if not classes:
        return {
            "is_dual_class": False,
            "num_classes": 0,
            "control_wedge": 0.0,
            "classes": [],
            "assessment": "Single share class — votes track economics.",
        }

    total_shares = sum((c.get("shares_outstanding") or 0.0) for c in classes)
    total_votes = sum(
        (c.get("shares_outstanding") or 0.0) * (c.get("votes_per_share") or 1.0) for c in classes
    )

    enriched = []
    max_vote_pct = 0.0
    for c in classes:
        shares = c.get("shares_outstanding") or 0.0
        vps = c.get("votes_per_share") or 1.0
        votes = shares * vps
        econ_pct = round(shares / total_shares * 100, 2) if total_shares else 0.0
        vote_pct = round(votes / total_votes * 100, 2) if total_votes else 0.0
        max_vote_pct = max(max_vote_pct, vote_pct)
        enriched.append({
            "class_name": c.get("class_name", "?"),
            "shares_outstanding": shares,
            "votes_per_share": vps,
            "economic_pct": econ_pct,
            "voting_pct": vote_pct,
            "wedge": round(vote_pct - econ_pct, 2),
        })

    vote_multiples = {(c.get("votes_per_share") or 1.0) for c in classes}
    is_dual_class = len(vote_multiples) > 1
    # Control wedge: largest gap between a class's voting and economic share.
    control_wedge = round(max((c["wedge"] for c in enriched), default=0.0), 2)

    if not is_dual_class:
        assessment = "Single voting tier — one-share-one-vote."
    elif control_wedge > 30:
        assessment = "Entrenched control: insiders' votes far exceed economic stake."
    elif control_wedge > 10:
        assessment = "Meaningful voting/economic divergence (founder control)."
    else:
        assessment = "Modest dual-class structure."

    return {
        "is_dual_class": is_dual_class,
        "num_classes": len(classes),
        "control_wedge": control_wedge,
        "max_voting_pct": round(max_vote_pct, 2),
        "classes": enriched,
        "assessment": assessment,
    }


# ── 3. Off-balance-sheet & VIE exposure ─────────────────────────────────

def analyze_off_balance_sheet(items: dict, total_assets: float | None = None) -> dict:
    """Quantify off-balance-sheet exposure relative to the balance sheet.

    items: operating_lease_commitments, purchase_obligations, guarantees,
    vie_assets, spe_exposure, unconsolidated_jv (all optional floats).
    """
    components = {
        "operating_lease_commitments": items.get("operating_lease_commitments") or 0.0,
        "purchase_obligations": items.get("purchase_obligations") or 0.0,
        "guarantees": items.get("guarantees") or 0.0,
        "vie_assets": items.get("vie_assets") or 0.0,
        "spe_exposure": items.get("spe_exposure") or 0.0,
        "unconsolidated_jv": items.get("unconsolidated_jv") or 0.0,
    }
    total_obs = round(sum(components.values()), 2)
    obs_to_assets = (
        round(total_obs / total_assets * 100, 1) if total_assets else None
    )

    if obs_to_assets is None:
        materiality = "UNKNOWN"
    elif obs_to_assets > 50:
        materiality = "HIGH"
    elif obs_to_assets > 20:
        materiality = "MODERATE"
    else:
        materiality = "LOW"

    return {
        "components": components,
        "total_off_balance_sheet": total_obs,
        "obs_to_assets_pct": obs_to_assets,
        "materiality": materiality,
        "has_vie": components["vie_assets"] > 0 or components["spe_exposure"] > 0,
    }


# ── 4. Debt subordination waterfall ─────────────────────────────────────

def analyze_debt_waterfall(tranches: list[dict]) -> dict:
    """Order debt by priority and assess structural/contractual subordination.

    Each tranche dict: instrument_name, principal_amount, seniority_rank
    (1 = most senior; lower number = higher priority), is_secured (bool),
    issuer_level ('OPCO'/'HOLDCO', optional).
    """
    if not tranches:
        return {"total_debt": 0.0, "layers": [], "secured_pct": 0.0,
                "structural_subordination": False, "assessment": "No debt on file."}

    total = sum((t.get("principal_amount") or 0.0) for t in tranches)
    secured = sum((t.get("principal_amount") or 0.0) for t in tranches if t.get("is_secured"))

    # Cumulative waterfall: how much debt sits ahead of each tranche.
    ranked = sorted(
        tranches,
        key=lambda t: (t.get("seniority_rank") if t.get("seniority_rank") is not None else 99,
                       0 if t.get("is_secured") else 1),
    )
    layers = []
    ahead = 0.0
    for t in ranked:
        principal = t.get("principal_amount") or 0.0
        layers.append({
            "instrument_name": t.get("instrument_name", "?"),
            "seniority_rank": t.get("seniority_rank"),
            "is_secured": bool(t.get("is_secured")),
            "issuer_level": t.get("issuer_level"),
            "principal_amount": principal,
            "debt_ahead": round(ahead, 2),
            "pct_of_total": round(principal / total * 100, 1) if total else 0.0,
        })
        ahead += principal

    levels = {(t.get("issuer_level") or "").upper() for t in tranches if t.get("issuer_level")}
    structural_subordination = "HOLDCO" in levels and "OPCO" in levels
    secured_pct = round(secured / total * 100, 1) if total else 0.0

    if structural_subordination:
        assessment = "Structural subordination: holdco debt sits behind opco creditors."
    elif secured_pct > 60:
        assessment = "Heavily secured — unsecured creditors deeply subordinated."
    else:
        assessment = "Conventional priority waterfall."

    return {
        "total_debt": round(total, 2),
        "num_tranches": len(tranches),
        "secured_pct": secured_pct,
        "structural_subordination": structural_subordination,
        "layers": layers,
        "assessment": assessment,
    }


# ── Orchestrator ────────────────────────────────────────────────────────

@dataclass
class StructureReport:
    subject: str | None = None
    subsidiary_tree: dict = field(default_factory=dict)
    share_classes: dict = field(default_factory=dict)
    off_balance_sheet: dict = field(default_factory=dict)
    debt_waterfall: dict = field(default_factory=dict)
    complexity_score: float = 0.0
    complexity_rating: str = "SIMPLE"
    flags: list[str] = field(default_factory=list)


def compute_complexity_score(tree: dict, classes: dict, obs: dict, waterfall: dict) -> float:
    """Blend the four dimensions into a 0–100 structural-complexity score."""
    score = 0.0
    # Subsidiary structure (max ~35).
    score += min(tree.get("distinct_jurisdictions", 0) * 1.5, 15)
    score += min(tree.get("offshore_pct", 0) * 0.3, 12)
    score += min(max(tree.get("max_depth", 1) - 1, 0) * 4, 8)
    # Equity control (max ~20).
    score += min(classes.get("control_wedge", 0) * 0.5, 20)
    # Off-balance-sheet (max ~20).
    if obs.get("obs_to_assets_pct"):
        score += min(obs["obs_to_assets_pct"] * 0.35, 18)
    if obs.get("has_vie"):
        score += 2
    # Debt structure (max ~25).
    if waterfall.get("structural_subordination"):
        score += 12
    score += min(waterfall.get("num_tranches", 0) * 1.0, 8)
    score += min(waterfall.get("secured_pct", 0) * 0.05, 5)
    return round(min(score, 100.0), 1)


def analyze_complex_structure(payload: dict, subject: str | None = None) -> StructureReport:
    """Full structural analysis from a combined payload.

    payload keys (all optional): subsidiaries (list), share_classes (list),
    off_balance_sheet (dict), total_assets (float), debt_tranches (list).
    """
    tree = analyze_subsidiary_tree(payload.get("subsidiaries", []), subject)
    classes = analyze_share_classes(payload.get("share_classes", []))
    obs = analyze_off_balance_sheet(
        payload.get("off_balance_sheet", {}), payload.get("total_assets")
    )
    waterfall = analyze_debt_waterfall(payload.get("debt_tranches", []))

    score = compute_complexity_score(tree, classes, obs, waterfall)
    rating = (
        "VERY_COMPLEX" if score >= 70
        else "COMPLEX" if score >= 45
        else "MODERATE" if score >= 25
        else "SIMPLE"
    )

    flags: list[str] = []
    if tree.get("complexity_flag"):
        flags.append("Sprawling / offshore-heavy subsidiary network")
    if classes.get("is_dual_class") and classes.get("control_wedge", 0) > 10:
        flags.append("Dual-class voting entrenchment")
    if obs.get("materiality") in ("MODERATE", "HIGH"):
        flags.append("Material off-balance-sheet exposure")
    if waterfall.get("structural_subordination"):
        flags.append("Structural subordination in debt stack")

    return StructureReport(
        subject=subject,
        subsidiary_tree=tree,
        share_classes=classes,
        off_balance_sheet=obs,
        debt_waterfall=waterfall,
        complexity_score=score,
        complexity_rating=rating,
        flags=flags,
    )
