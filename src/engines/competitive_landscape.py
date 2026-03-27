"""Pillar 3 Phase 3A — Competitive Landscape Engine.

Pure computation engine for competitive landscape analysis.
Evaluates market share, peer comparisons, value chain positioning,
competitive advantages, and competitive threats.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class PeerComparison:
    """Single peer entity comparison data."""

    entity_id: str
    name: str
    market_cap: float
    market_share_est: float | None = None
    revenue_growth: float | None = None
    operating_margin: float | None = None
    roic: float | None = None
    pe_ratio: float | None = None


@dataclass
class LandscapeResult:
    """Complete competitive landscape analysis."""

    peer_group: list[PeerComparison] = field(default_factory=list)
    entity_rank: int = 0  # among peers by market cap
    market_share_est: float | None = None
    share_gainer: bool = False
    revenue_growth_vs_peers: float = 0.0  # entity - peer median
    margin_vs_peers: float = 0.0
    roic_vs_peers: float = 0.0
    value_chain_position: str = "INTEGRATED"
    competitive_advantages: list[str] = field(default_factory=list)
    competitive_threats: list[str] = field(default_factory=list)


# ── Market Share ─────────────────────────────────────────────────────────


def estimate_market_share(
    entity_revenue: float,
    total_industry_revenue: float,
) -> float:
    """Estimate market share as entity revenue / total industry revenue.

    Parameters
    ----------
    entity_revenue : float
        Entity revenue.
    total_industry_revenue : float
        Total addressable industry revenue.

    Returns
    -------
    float
        Market share as a decimal (e.g. 0.20 = 20%). Zero if industry is zero.
    """
    if total_industry_revenue <= 0:
        return 0.0
    return round(entity_revenue / total_industry_revenue, 4)


# ── Share Gainer Detection ───────────────────────────────────────────────


def detect_share_gainer(
    entity_growth: float,
    industry_growth: float,
    threshold: float = 2.0,
) -> bool:
    """Detect if entity is gaining market share.

    Parameters
    ----------
    entity_growth : float
        Entity revenue growth (percentage points, e.g. 12.0 = 12%).
    industry_growth : float
        Industry revenue growth (percentage points).
    threshold : float
        Minimum outperformance in pp to qualify as a gainer.

    Returns
    -------
    bool
        True if entity outperforms industry by > threshold pp.
    """
    return (entity_growth - industry_growth) > threshold


# ── Value Chain Position ─────────────────────────────────────────────────


def classify_value_chain_position(
    segment_data: dict | None,
    industry_keywords: dict | None,
) -> str:
    """Classify value chain position.

    Parameters
    ----------
    segment_data : dict | None
        Segment data with keys like 'segments' containing segment names.
    industry_keywords : dict | None
        Keyword mappings for classification:
        - upstream: list[str]
        - midstream: list[str]
        - downstream: list[str]

    Returns
    -------
    str
        UPSTREAM, MIDSTREAM, DOWNSTREAM, or INTEGRATED.
    """
    if not segment_data and not industry_keywords:
        return "INTEGRATED"

    # Default keyword sets if not provided
    if industry_keywords is None:
        industry_keywords = {
            "upstream": ["mining", "extraction", "exploration", "raw material", "drilling"],
            "midstream": ["manufacturing", "processing", "refining", "assembly", "production"],
            "downstream": ["retail", "distribution", "consumer", "sales", "service", "store"],
        }

    # Check segment names for keywords
    segments = segment_data.get("segments", []) if segment_data else []
    if isinstance(segments, list):
        segment_text = " ".join(
            (s.get("name", "") if isinstance(s, dict) else str(s)) for s in segments
        ).lower()
    else:
        segment_text = ""

    # Also check description
    description = (segment_data or {}).get("description", "").lower()
    combined = segment_text + " " + description

    matches = {"upstream": 0, "midstream": 0, "downstream": 0}
    for position, keywords in industry_keywords.items():
        if position in matches:
            matches[position] = sum(1 for kw in keywords if kw in combined)

    total_matches = sum(matches.values())
    if total_matches == 0:
        return "INTEGRATED"

    # If multiple positions have significant matches -> INTEGRATED
    active_positions = sum(1 for v in matches.values() if v > 0)
    if active_positions >= 2:
        # Check if one dominates
        max_match = max(matches.values())
        if max_match > total_matches * 0.6:
            return max(matches, key=matches.get).upper()
        return "INTEGRATED"

    return max(matches, key=matches.get).upper()


# ── Peer Group Construction ──────────────────────────────────────────────


def build_peer_group(
    target_entity: dict,
    all_companies: list[dict],
    max_peers: int = 10,
) -> list[PeerComparison]:
    """Select peers by same GICS + similar market cap.

    Parameters
    ----------
    target_entity : dict
        Target entity with keys:
        - entity_id: str
        - gics_sector: str
        - gics_industry: str
        - market_cap: float
    all_companies : list[dict]
        All candidate companies with same keys plus name,
        revenue_growth, operating_margin, roic, pe_ratio, market_share_est.
    max_peers : int
        Maximum number of peers to return.

    Returns
    -------
    list[PeerComparison]
        Sorted by market cap proximity to target.
    """
    target_id = target_entity.get("entity_id", "")
    target_gics = target_entity.get("gics_industry", "")
    target_sector = target_entity.get("gics_sector", "")
    target_mcap = target_entity.get("market_cap", 0)

    # Filter: same GICS industry (or sector if industry yields too few)
    candidates = [
        c for c in all_companies
        if c.get("entity_id") != target_id
        and c.get("gics_industry") == target_gics
    ]

    # Fall back to sector if too few industry peers
    if len(candidates) < 3:
        candidates = [
            c for c in all_companies
            if c.get("entity_id") != target_id
            and c.get("gics_sector") == target_sector
        ]

    # Sort by market cap proximity
    candidates.sort(key=lambda c: abs(c.get("market_cap", 0) - target_mcap))

    # Take top N
    peers = candidates[:max_peers]

    return [
        PeerComparison(
            entity_id=c.get("entity_id", ""),
            name=c.get("name", ""),
            market_cap=c.get("market_cap", 0),
            market_share_est=c.get("market_share_est"),
            revenue_growth=c.get("revenue_growth"),
            operating_margin=c.get("operating_margin"),
            roic=c.get("roic"),
            pe_ratio=c.get("pe_ratio"),
        )
        for c in peers
    ]


# ── Peer-Relative Metrics ───────────────────────────────────────────────


def compute_peer_relative_metrics(
    entity_data: dict,
    peer_group: list[PeerComparison],
) -> dict:
    """Compute entity metrics relative to peer medians.

    Parameters
    ----------
    entity_data : dict
        Entity metrics: revenue_growth, operating_margin, roic.
    peer_group : list[PeerComparison]
        Peer group for comparison.

    Returns
    -------
    dict
        {metric: entity_value - peer_median} for growth, margin, roic.
    """
    result: dict = {}

    # Revenue growth vs peers
    peer_growths = [p.revenue_growth for p in peer_group if p.revenue_growth is not None]
    entity_growth = entity_data.get("revenue_growth")
    if entity_growth is not None and peer_growths:
        peer_med = statistics.median(peer_growths)
        result["revenue_growth_vs_peers"] = round(entity_growth - peer_med, 4)

    # Operating margin vs peers
    peer_margins = [p.operating_margin for p in peer_group if p.operating_margin is not None]
    entity_margin = entity_data.get("operating_margin")
    if entity_margin is not None and peer_margins:
        peer_med = statistics.median(peer_margins)
        result["margin_vs_peers"] = round(entity_margin - peer_med, 4)

    # ROIC vs peers
    peer_roics = [p.roic for p in peer_group if p.roic is not None]
    entity_roic = entity_data.get("roic")
    if entity_roic is not None and peer_roics:
        peer_med = statistics.median(peer_roics)
        result["roic_vs_peers"] = round(entity_roic - peer_med, 4)

    return result


# ── Competitive Advantages ───────────────────────────────────────────────


def identify_competitive_advantages(
    entity_data: dict,
    peer_medians: dict,
) -> list[str]:
    """Identify competitive advantages vs peers.

    Parameters
    ----------
    entity_data : dict
        Entity metrics.
    peer_medians : dict
        Peer median values for comparison.

    Returns
    -------
    list[str]
        List of advantage descriptions.
    """
    advantages: list[str] = []

    # Margin advantage
    entity_margin = entity_data.get("operating_margin")
    peer_margin = peer_medians.get("operating_margin")
    if entity_margin is not None and peer_margin is not None:
        spread = entity_margin - peer_margin
        if spread > 0.05:
            advantages.append(
                f"Superior margin structure ({entity_margin:.1%} vs peer {peer_margin:.1%})"
            )

    # ROIC advantage
    entity_roic = entity_data.get("roic")
    peer_roic = peer_medians.get("roic")
    if entity_roic is not None and peer_roic is not None:
        if entity_roic - peer_roic > 0.03:
            advantages.append(
                f"Higher capital efficiency (ROIC {entity_roic:.1%} vs peer {peer_roic:.1%})"
            )

    # Growth advantage
    entity_growth = entity_data.get("revenue_growth")
    peer_growth = peer_medians.get("revenue_growth")
    if entity_growth is not None and peer_growth is not None:
        if entity_growth - peer_growth > 3.0:
            advantages.append(
                f"Faster revenue growth ({entity_growth:.1f}% vs peer {peer_growth:.1f}%)"
            )

    # Market share advantage
    entity_share = entity_data.get("market_share")
    if entity_share is not None and entity_share > 0.25:
        advantages.append(f"Dominant market position ({entity_share:.0%} share)")

    # Valuation discount (lower P/E can be advantage for value)
    entity_pe = entity_data.get("pe_ratio")
    peer_pe = peer_medians.get("pe_ratio")
    if entity_pe is not None and peer_pe is not None and peer_pe > 0:
        if entity_pe < peer_pe * 0.8:
            advantages.append(
                f"Valuation discount (P/E {entity_pe:.1f}x vs peer {peer_pe:.1f}x)"
            )

    return advantages


# ── Competitive Threats ──────────────────────────────────────────────────


def identify_competitive_threats(
    entity_data: dict,
    industry_trends: dict | None,
) -> list[str]:
    """Identify competitive threats.

    Parameters
    ----------
    entity_data : dict
        Entity metrics including share_trend, margin_trend, etc.
    industry_trends : dict | None
        Industry-level trends.

    Returns
    -------
    list[str]
        List of threat descriptions.
    """
    threats: list[str] = []

    # Market share erosion
    share_trend = entity_data.get("share_trend", "STABLE")
    if share_trend == "LOSING":
        threats.append("Market share erosion: losing share to competitors")

    # Margin pressure
    margin_trend = entity_data.get("margin_trend")
    if margin_trend is not None and margin_trend < -0.02:
        threats.append("Margin pressure: operating margins declining")

    # Revenue growth lagging
    entity_growth = entity_data.get("revenue_growth")
    industry_growth = (industry_trends or {}).get("revenue_growth")
    if entity_growth is not None and industry_growth is not None:
        if industry_growth - entity_growth > 3.0:
            threats.append("Revenue growth lagging industry average")

    # Competitive intensity
    new_entrants = (industry_trends or {}).get("new_entrants")
    if new_entrants is not None and new_entrants > 5:
        threats.append(f"High competitive intensity: {new_entrants} new entrants in market")

    # Technology disruption
    disruption_risk = (industry_trends or {}).get("disruption_risk")
    if disruption_risk is not None and disruption_risk > 0.6:
        threats.append("Technology disruption risk: industry faces significant disruption")

    # Regulatory risk
    regulatory_risk = (industry_trends or {}).get("regulatory_risk")
    if regulatory_risk is not None and regulatory_risk > 0.6:
        threats.append("Regulatory headwinds: increased regulatory burden expected")

    return threats


# ── Full Orchestrator ────────────────────────────────────────────────────


def analyze_competitive_landscape(
    entity_data: dict,
    all_companies: list[dict],
    industry_stats: dict,
) -> LandscapeResult:
    """Full competitive landscape analysis orchestrator.

    Parameters
    ----------
    entity_data : dict
        Entity data including:
        - entity_id, name, gics_sector, gics_industry, market_cap
        - revenue, revenue_growth, operating_margin, roic, pe_ratio
        - segment_data: dict | None
        - share_trend: str
        - margin_trend: float | None
        - market_share: float | None
    all_companies : list[dict]
        All candidate peer companies.
    industry_stats : dict
        - total_industry_revenue: float
        - revenue_growth: float (industry average)
        - industry_keywords: dict | None
        - new_entrants: int | None
        - disruption_risk: float | None
        - regulatory_risk: float | None

    Returns
    -------
    LandscapeResult
    """
    # 1. Estimate market share
    entity_revenue = entity_data.get("revenue", 0)
    total_industry_rev = industry_stats.get("total_industry_revenue", 0)
    market_share = entity_data.get("market_share")
    if market_share is None:
        market_share = estimate_market_share(entity_revenue, total_industry_rev)

    # 2. Detect share gainer
    entity_growth = entity_data.get("revenue_growth", 0)
    industry_growth = industry_stats.get("revenue_growth", 0)
    share_gainer = detect_share_gainer(entity_growth, industry_growth)

    # 3. Value chain position
    segment_data = entity_data.get("segment_data")
    industry_keywords = industry_stats.get("industry_keywords")
    value_chain = classify_value_chain_position(segment_data, industry_keywords)

    # 4. Build peer group
    peer_group = build_peer_group(entity_data, all_companies)

    # 5. Entity rank by market cap among peers
    entity_mcap = entity_data.get("market_cap", 0)
    all_mcaps = [entity_mcap] + [p.market_cap for p in peer_group]
    all_mcaps.sort(reverse=True)
    entity_rank = all_mcaps.index(entity_mcap) + 1 if entity_mcap in all_mcaps else 0

    # 6. Peer-relative metrics
    relative = compute_peer_relative_metrics(entity_data, peer_group)

    # 7. Compute peer medians for advantage/threat detection
    peer_margins = [p.operating_margin for p in peer_group if p.operating_margin is not None]
    peer_roics = [p.roic for p in peer_group if p.roic is not None]
    peer_growths = [p.revenue_growth for p in peer_group if p.revenue_growth is not None]
    peer_pes = [p.pe_ratio for p in peer_group if p.pe_ratio is not None]

    peer_medians = {}
    if peer_margins:
        peer_medians["operating_margin"] = statistics.median(peer_margins)
    if peer_roics:
        peer_medians["roic"] = statistics.median(peer_roics)
    if peer_growths:
        peer_medians["revenue_growth"] = statistics.median(peer_growths)
    if peer_pes:
        peer_medians["pe_ratio"] = statistics.median(peer_pes)

    # 8. Competitive advantages and threats
    advantages = identify_competitive_advantages(entity_data, peer_medians)
    threats = identify_competitive_threats(entity_data, industry_stats)

    return LandscapeResult(
        peer_group=peer_group,
        entity_rank=entity_rank,
        market_share_est=market_share,
        share_gainer=share_gainer,
        revenue_growth_vs_peers=relative.get("revenue_growth_vs_peers", 0.0),
        margin_vs_peers=relative.get("margin_vs_peers", 0.0),
        roic_vs_peers=relative.get("roic_vs_peers", 0.0),
        value_chain_position=value_chain,
        competitive_advantages=advantages,
        competitive_threats=threats,
    )
