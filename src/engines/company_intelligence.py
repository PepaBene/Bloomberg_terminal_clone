"""Company Intelligence Engine.

Assembles data for company briefings and optionally generates AI narrative.
Pure computation functions do NOT access the database — they operate on
pre-fetched data dicts passed in by the router layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KeySignal:
    """A key intelligence signal detected from data."""
    signal: str
    severity: str  # HIGH, MEDIUM, LOW
    detail: str | None = None


@dataclass
class ValuationContext:
    """Valuation context computed from fundamentals."""
    pe_current: float | None = None
    pe_5y_avg: float | None = None
    pe_vs_peers: float | None = None
    ev_ebitda: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None


@dataclass
class BriefingData:
    """Assembled briefing data snapshot."""
    entity_id: str
    entity_name: str | None = None
    key_signals: list[KeySignal] = field(default_factory=list)
    valuation_context: ValuationContext | None = None
    summary_text: str | None = None
    ai_enabled: bool = False


def extract_key_signals(data: dict) -> list[KeySignal]:
    """Extract key intelligence signals from assembled data.

    Pure computation — always works regardless of AI availability.

    Parameters
    ----------
    data : dict with optional keys:
        - price_change_pct: float (recent price change %)
        - volume_ratio: float (current / average volume)
        - earnings_surprise_pct: float
        - insider_net_shares: float (positive = buying)
        - debt_to_equity: float
        - interest_coverage: float
        - guidance_revision: str (UP/DOWN/UNCHANGED)
        - analyst_revision_pct: float

    Returns
    -------
    list of KeySignal
    """
    signals = []

    # Price momentum signals
    price_change = data.get("price_change_pct")
    if price_change is not None:
        if price_change > 10:
            signals.append(KeySignal(
                signal="Strong positive momentum",
                severity="HIGH",
                detail=f"Price up {price_change:.1f}% recently",
            ))
        elif price_change < -10:
            signals.append(KeySignal(
                signal="Significant price decline",
                severity="HIGH",
                detail=f"Price down {abs(price_change):.1f}% recently",
            ))

    # Volume signals
    volume_ratio = data.get("volume_ratio")
    if volume_ratio is not None and volume_ratio > 3.0:
        signals.append(KeySignal(
            signal="Unusual volume activity",
            severity="MEDIUM",
            detail=f"Volume {volume_ratio:.1f}x average",
        ))

    # Earnings surprise
    earnings_surprise = data.get("earnings_surprise_pct")
    if earnings_surprise is not None:
        if earnings_surprise > 10:
            signals.append(KeySignal(
                signal="Strong earnings beat",
                severity="HIGH",
                detail=f"Beat estimates by {earnings_surprise:.1f}%",
            ))
        elif earnings_surprise < -10:
            signals.append(KeySignal(
                signal="Significant earnings miss",
                severity="HIGH",
                detail=f"Missed estimates by {abs(earnings_surprise):.1f}%",
            ))

    # Insider activity
    insider_shares = data.get("insider_net_shares")
    if insider_shares is not None:
        if insider_shares > 0:
            signals.append(KeySignal(
                signal="Insider buying detected",
                severity="MEDIUM",
                detail=f"Net insider purchases: {insider_shares:,.0f} shares",
            ))
        elif insider_shares < -100000:
            signals.append(KeySignal(
                signal="Significant insider selling",
                severity="MEDIUM",
                detail=f"Net insider sales: {abs(insider_shares):,.0f} shares",
            ))

    # Credit / leverage signals
    debt_to_equity = data.get("debt_to_equity")
    if debt_to_equity is not None and debt_to_equity > 3.0:
        signals.append(KeySignal(
            signal="High leverage warning",
            severity="HIGH",
            detail=f"Debt/Equity ratio: {debt_to_equity:.1f}x",
        ))

    interest_coverage = data.get("interest_coverage")
    if interest_coverage is not None and interest_coverage < 1.5:
        signals.append(KeySignal(
            signal="Low interest coverage",
            severity="HIGH",
            detail=f"Interest coverage: {interest_coverage:.1f}x",
        ))

    # Guidance revision
    guidance = data.get("guidance_revision")
    if guidance == "UP":
        signals.append(KeySignal(
            signal="Management raised guidance",
            severity="MEDIUM",
            detail="Positive guidance revision",
        ))
    elif guidance == "DOWN":
        signals.append(KeySignal(
            signal="Management lowered guidance",
            severity="HIGH",
            detail="Negative guidance revision",
        ))

    # Analyst revisions
    analyst_rev = data.get("analyst_revision_pct")
    if analyst_rev is not None:
        if analyst_rev > 5:
            signals.append(KeySignal(
                signal="Positive analyst revisions",
                severity="MEDIUM",
                detail=f"Estimates revised up {analyst_rev:.1f}%",
            ))
        elif analyst_rev < -5:
            signals.append(KeySignal(
                signal="Negative analyst revisions",
                severity="MEDIUM",
                detail=f"Estimates revised down {abs(analyst_rev):.1f}%",
            ))

    return signals


def compute_valuation_context(data: dict) -> ValuationContext:
    """Compute valuation context from fundamental data.

    Pure computation — always works regardless of AI availability.

    Parameters
    ----------
    data : dict with optional keys:
        - price, eps, pe_5y_avg, peer_pe_avg, ev, ebitda,
          book_value_per_share, dividend_per_share

    Returns
    -------
    ValuationContext
    """
    price = data.get("price")
    eps = data.get("eps")

    pe_current = None
    if price is not None and eps is not None and eps > 0:
        pe_current = round(price / eps, 2)

    pe_5y_avg = data.get("pe_5y_avg")
    peer_pe = data.get("peer_pe_avg")

    pe_vs_peers = None
    if pe_current is not None and peer_pe is not None and peer_pe > 0:
        pe_vs_peers = round(pe_current / peer_pe, 2)

    ev = data.get("ev")
    ebitda = data.get("ebitda")
    ev_ebitda = None
    if ev is not None and ebitda is not None and ebitda > 0:
        ev_ebitda = round(ev / ebitda, 2)

    bvps = data.get("book_value_per_share")
    pb_ratio = None
    if price is not None and bvps is not None and bvps > 0:
        pb_ratio = round(price / bvps, 2)

    dps = data.get("dividend_per_share")
    div_yield = None
    if price is not None and dps is not None and price > 0:
        div_yield = round(dps / price * 100, 2)

    return ValuationContext(
        pe_current=pe_current,
        pe_5y_avg=pe_5y_avg,
        pe_vs_peers=pe_vs_peers,
        ev_ebitda=ev_ebitda,
        pb_ratio=pb_ratio,
        dividend_yield=div_yield,
    )


def generate_briefing(
    entity_id: str,
    entity_name: str | None,
    signal_data: dict,
    valuation_data: dict,
    ai_summary: str | None = None,
) -> BriefingData:
    """Generate a company briefing from assembled data.

    Parameters
    ----------
    entity_id : Entity UUID string.
    entity_name : Company name.
    signal_data : Data dict for extract_key_signals.
    valuation_data : Data dict for compute_valuation_context.
    ai_summary : Optional AI-generated summary text (None when AI disabled).

    Returns
    -------
    BriefingData with all fields populated.
    """
    signals = extract_key_signals(signal_data)
    valuation = compute_valuation_context(valuation_data)

    return BriefingData(
        entity_id=entity_id,
        entity_name=entity_name,
        key_signals=signals,
        valuation_context=valuation,
        summary_text=ai_summary,
        ai_enabled=ai_summary is not None,
    )
