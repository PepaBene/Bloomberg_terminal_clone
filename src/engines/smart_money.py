"""Smart-Money / Notable-Filer Intelligence Engine.

Tracks the disclosed activity of notable investors, corporate insiders, and
politicians ("follow Michael Burry, Jamie Dimon, Nancy Pelosi") and turns it
into structured, comparable follow-signals.

All inputs come from FREE public data already ingested by the platform:
  - GURU_13F      → SEC EDGAR 13F-HR institutional holdings (quarter diffs)
  - INSIDER_FORM4 → SEC EDGAR Form 4 insider transactions
  - POLITICIAN    → US Congress STOCK Act periodic transaction reports

Pure computation — no database or network access. The router/loader supplies
pre-fetched holding/transaction dicts and the curated registry entry; every
function here accepts and returns plain data so it is trivially testable.
"""

from __future__ import annotations

import json
import os
from datetime import date


# ── Constants ──────────────────────────────────────────────────────────

#: Relative trust/impact weight of each follow category. Insiders trading
#: their own company's stock on the open market carry the strongest signal,
#: followed by concentrated 13F managers, then politicians (disclosure lag).
CATEGORY_SIGNAL_WEIGHTS: dict[str, float] = {
    "INSIDER_FORM4": 1.0,
    "GURU_13F": 0.85,
    "POLITICIAN": 0.6,
}

#: Bullish vs bearish direction for each normalized action.
ACTION_DIRECTION: dict[str, str] = {
    "NEW": "BULLISH",
    "BUY": "BULLISH",
    "ADD": "BULLISH",
    "EXIT": "BEARISH",
    "SELL": "BEARISH",
    "TRIM": "BEARISH",
    "HOLD": "NEUTRAL",
}

#: STOCK Act requires disclosure within 45 days of a transaction.
STOCK_ACT_DISCLOSURE_DEADLINE_DAYS: int = 45

#: Congressional committee → GICS sectors whose oversight could create a
#: perceived conflict of interest when a member trades the sector.
COMMITTEE_SECTOR_JURISDICTION: dict[str, list[str]] = {
    "ENERGY AND COMMERCE": ["ENERGY", "HEALTH_CARE", "COMMUNICATION_SERVICES", "UTILITIES"],
    "FINANCIAL SERVICES": ["FINANCIALS"],
    "ARMED SERVICES": ["INDUSTRIALS"],
    "HEALTH": ["HEALTH_CARE"],
    "AGRICULTURE": ["CONSUMER_STAPLES", "MATERIALS"],
    "SCIENCE SPACE AND TECHNOLOGY": ["INFORMATION_TECHNOLOGY"],
    "TRANSPORTATION AND INFRASTRUCTURE": ["INDUSTRIALS"],
    "WAYS AND MEANS": ["ALL"],
}

#: Dollar-range buckets for sizing congressional / insider trades.
_SIZE_BUCKETS: list[tuple[float, str]] = [
    (15_000, "SMALL"),
    (100_000, "MODERATE"),
    (500_000, "LARGE"),
    (1_000_000, "VERY_LARGE"),
    (float("inf"), "JUMBO"),
]


# ── Registry loader (static config — same role as reference data) ───────

def load_notable_investors(path: str | None = None) -> list[dict]:
    """Load the curated notable-investor registry from ``data/``.

    Returns the list of registry entries. Missing file → empty list so the
    feature degrades gracefully rather than raising.
    """
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "notable_investors.json",
        )
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload.get("investors", [])


def find_investor(registry: list[dict], query: str) -> dict | None:
    """Resolve a free-text query (key or display name) to a registry entry."""
    q = (query or "").strip().lower()
    if not q:
        return None
    for entry in registry:
        if entry.get("key", "").lower() == q:
            return entry
        if entry.get("display_name", "").lower() == q:
            return entry
    # Fuzzy contains match on display name as a fallback.
    for entry in registry:
        if q in entry.get("display_name", "").lower():
            return entry
    return None


# ── Conviction scoring ──────────────────────────────────────────────────

def compute_position_conviction(position: dict) -> float:
    """Score how high-conviction a single holding is, on a 0–100 scale.

    Combines portfolio weight (primary driver), absolute size, and recent
    accumulation. A brand-new position or a heavily-weighted one scores high.

    Parameters
    ----------
    position : dict with optional keys
        - percent_of_portfolio : float (0–100)
        - market_value : float
        - is_new_position : bool
        - shares_change_pct : float (e.g. 0.5 = +50% QoQ)
    """
    weight = position.get("percent_of_portfolio") or 0.0
    # Portfolio weight contributes up to 60 points (caps at a 20% position).
    weight_score = min(weight / 20.0, 1.0) * 60.0

    mv = position.get("market_value") or 0.0
    # Absolute size contributes up to 20 points (caps at $1B).
    size_score = min(mv / 1_000_000_000.0, 1.0) * 20.0

    momentum_score = 0.0
    if position.get("is_new_position"):
        momentum_score = 20.0
    else:
        chg = position.get("shares_change_pct")
        if chg is not None and chg > 0:
            momentum_score = min(chg, 1.0) * 20.0

    return round(weight_score + size_score + momentum_score, 1)


# ── 13F filer profile (quarter-over-quarter diff) ───────────────────────

def _index_by_security(holdings: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for h in holdings:
        key = h.get("ticker") or h.get("security_id") or h.get("name")
        if key is not None:
            out[str(key)] = h
    return out


def build_filer_profile(
    display_name: str,
    category: str,
    current_holdings: list[dict],
    prior_holdings: list[dict] | None = None,
) -> dict:
    """Build an activity profile for a 13F manager from current vs prior holdings.

    Each holding dict should carry: ticker/name, market_value,
    percent_of_portfolio, shares (or shares_held). Returns a structured
    profile with new/exited/increased/decreased positions, top holdings,
    concentration, and portfolio turnover.
    """
    current = _index_by_security(current_holdings)
    prior = _index_by_security(prior_holdings or [])

    new_positions, increased, decreased, unchanged = [], [], [], []
    for key, h in current.items():
        cur_shares = h.get("shares") or h.get("shares_held") or 0.0
        conviction = compute_position_conviction(h)
        enriched = {**h, "conviction": conviction}
        if key not in prior:
            enriched["is_new_position"] = True
            enriched["conviction"] = compute_position_conviction({**h, "is_new_position": True})
            new_positions.append(enriched)
            continue
        prev_shares = prior[key].get("shares") or prior[key].get("shares_held") or 0.0
        if prev_shares and cur_shares > prev_shares:
            enriched["shares_change_pct"] = round((cur_shares - prev_shares) / prev_shares, 4)
            increased.append(enriched)
        elif prev_shares and cur_shares < prev_shares:
            enriched["shares_change_pct"] = round((cur_shares - prev_shares) / prev_shares, 4)
            decreased.append(enriched)
        else:
            unchanged.append(enriched)

    exited_positions = [
        {**prior[key], "is_exit": True} for key in prior if key not in current
    ]

    ranked = sorted(
        current.values(),
        key=lambda h: h.get("percent_of_portfolio") or 0.0,
        reverse=True,
    )
    top5 = ranked[:5]
    concentration = round(sum((h.get("percent_of_portfolio") or 0.0) for h in top5), 2)
    total_value = round(sum((h.get("market_value") or 0.0) for h in current.values()), 2)

    # Turnover proxy: share of names that changed this quarter.
    changed = len(new_positions) + len(exited_positions)
    universe = max(len(set(current) | set(prior)), 1)
    turnover = round(changed / universe, 4)

    return {
        "display_name": display_name,
        "category": category,
        "num_holdings": len(current),
        "total_value": total_value,
        "top5_concentration_pct": concentration,
        "turnover": turnover,
        "new_positions": sorted(new_positions, key=lambda h: h["conviction"], reverse=True),
        "exited_positions": exited_positions,
        "increased_positions": sorted(increased, key=lambda h: h.get("shares_change_pct", 0), reverse=True),
        "decreased_positions": decreased,
        "top_holdings": top5,
    }


# ── Politician (STOCK Act) trade classification ─────────────────────────

def _size_bucket(amount: float) -> str:
    for threshold, label in _SIZE_BUCKETS:
        if amount <= threshold:
            return label
    return "JUMBO"


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def classify_political_trade(trade: dict, committees: list[str] | None = None) -> dict:
    """Annotate a congressional trade with size, disclosure lag, and conflict flags.

    Parameters
    ----------
    trade : dict
        transaction_type (BUY/SELL/EXCHANGE), amount_range_low, amount_range_high,
        transaction_date, disclosure_date, sector (optional GICS).
    committees : list[str] | None
        Committee assignments of the member (for conflict-of-interest flagging).
    """
    low = trade.get("amount_range_low") or 0.0
    high = trade.get("amount_range_high") or low
    midpoint = round((low + high) / 2.0, 2)

    tx_date = _parse_date(trade.get("transaction_date"))
    disc_date = _parse_date(trade.get("disclosure_date"))
    lag = (disc_date - tx_date).days if (tx_date and disc_date) else None

    sector = (trade.get("sector") or "").upper()
    conflict = False
    conflict_committee = None
    for committee in (committees or []):
        jurisdiction = COMMITTEE_SECTOR_JURISDICTION.get(committee.strip().upper(), [])
        if sector and (sector in jurisdiction or "ALL" in jurisdiction):
            conflict = True
            conflict_committee = committee
            break

    return {
        **trade,
        "midpoint_amount": midpoint,
        "size_bucket": _size_bucket(midpoint),
        "disclosure_lag_days": lag,
        "is_late_disclosure": (lag is not None and lag > STOCK_ACT_DISCLOSURE_DEADLINE_DAYS),
        "committee_conflict": conflict,
        "conflict_committee": conflict_committee,
    }


# ── Unified follow-signal ───────────────────────────────────────────────

def compute_follow_signal(event: dict) -> dict:
    """Convert a single notable-filer event into a directional follow-signal.

    Parameters
    ----------
    event : dict
        - category : one of CATEGORY_SIGNAL_WEIGHTS
        - action : NEW/BUY/ADD/EXIT/SELL/TRIM/HOLD
        - conviction : float 0–100 (optional, defaults 50)
        - is_open_market : bool (optional, insiders) — non-open-market halves strength
        - is_late_disclosure : bool (optional, politicians) — decays strength
        - committee_conflict : bool (optional, politicians) — boosts notability

    Returns dict: {direction, strength (0–100), rationale}.
    """
    category = event.get("category", "GURU_13F")
    action = (event.get("action") or "HOLD").upper()
    direction = ACTION_DIRECTION.get(action, "NEUTRAL")
    base_weight = CATEGORY_SIGNAL_WEIGHTS.get(category, 0.5)
    conviction = event.get("conviction")
    conviction = 50.0 if conviction is None else float(conviction)

    strength = base_weight * conviction  # 0–100 before adjustments
    rationale: list[str] = [f"{category} {action} (conviction {conviction:.0f})"]

    if category == "INSIDER_FORM4":
        if event.get("is_open_market") is False:
            strength *= 0.5
            rationale.append("non-open-market (grant/exercise) — discounted")
        elif event.get("is_open_market"):
            strength *= 1.15
            rationale.append("open-market transaction — emphasized")

    if category == "POLITICIAN":
        if event.get("is_late_disclosure"):
            strength *= 0.8
            rationale.append("late STOCK Act disclosure — staleness discount")
        if event.get("committee_conflict"):
            strength *= 1.2
            rationale.append("trade overlaps committee jurisdiction — elevated scrutiny")

    strength = round(max(0.0, min(strength, 100.0)), 1)
    return {"direction": direction, "strength": strength, "rationale": "; ".join(rationale)}


# ── Cross-investor consensus / smart-money flow ─────────────────────────

def detect_consensus(profiles: list[dict], min_participants: int = 2) -> list[dict]:
    """Find securities that multiple tracked filers are accumulating or exiting.

    Consumes a list of profiles from :func:`build_filer_profile`. A security
    counts as a buy for a filer if it is a new or increased position, and a
    sell if exited or decreased. Returns consensus rows sorted by net score.
    """
    tally: dict[str, dict] = {}

    def _key(h: dict) -> str | None:
        k = h.get("ticker") or h.get("name") or h.get("security_id")
        return str(k) if k is not None else None

    for prof in profiles:
        name = prof.get("display_name", "?")
        for h in prof.get("new_positions", []) + prof.get("increased_positions", []):
            k = _key(h)
            if not k:
                continue
            row = tally.setdefault(k, {"ticker": k, "buyers": [], "sellers": []})
            if name not in row["buyers"]:
                row["buyers"].append(name)
        for h in prof.get("exited_positions", []) + prof.get("decreased_positions", []):
            k = _key(h)
            if not k:
                continue
            row = tally.setdefault(k, {"ticker": k, "buyers": [], "sellers": []})
            if name not in row["sellers"]:
                row["sellers"].append(name)

    results = []
    for row in tally.values():
        n_buy, n_sell = len(row["buyers"]), len(row["sellers"])
        participants = n_buy + n_sell
        if participants < min_participants:
            continue
        net = n_buy - n_sell
        row["net_score"] = net
        row["participants"] = participants
        row["signal"] = "BULLISH" if net > 0 else "BEARISH" if net < 0 else "MIXED"
        results.append(row)

    return sorted(results, key=lambda r: (abs(r["net_score"]), r["participants"]), reverse=True)


def aggregate_smart_money_flow(events: list[dict]) -> list[dict]:
    """Aggregate per-security net smart-money pressure from follow-signal events.

    Each event must include ``ticker`` plus the output of
    :func:`compute_follow_signal` (direction, strength). Returns per-ticker
    net pressure (bullish strength minus bearish strength), sorted by
    absolute pressure.
    """
    by_ticker: dict[str, dict] = {}
    for ev in events:
        ticker = ev.get("ticker")
        if not ticker:
            continue
        row = by_ticker.setdefault(
            ticker,
            {"ticker": ticker, "bullish": 0.0, "bearish": 0.0, "events": 0, "names": []},
        )
        strength = float(ev.get("strength", 0.0))
        if ev.get("direction") == "BULLISH":
            row["bullish"] += strength
        elif ev.get("direction") == "BEARISH":
            row["bearish"] += strength
        row["events"] += 1
        nm = ev.get("display_name")
        if nm and nm not in row["names"]:
            row["names"].append(nm)

    out = []
    for row in by_ticker.values():
        row["net_pressure"] = round(row["bullish"] - row["bearish"], 1)
        row["signal"] = (
            "BULLISH" if row["net_pressure"] > 0
            else "BEARISH" if row["net_pressure"] < 0 else "NEUTRAL"
        )
        out.append(row)
    return sorted(out, key=lambda r: abs(r["net_pressure"]), reverse=True)
