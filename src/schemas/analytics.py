"""Pillar 2: Analytics Engine schemas (Spec §14 standard envelope).

All analytics API responses use the AnalyticsResponse envelope which
wraps metrics with metadata (cache_hit, processing_time, freshness).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Standard response envelope (Spec §14)
# ---------------------------------------------------------------------------

class MetricValue(BaseModel):
    """Single metric inside the standard envelope."""

    value: float | None = None
    unit: str = "ratio"
    period: str = "TTM"
    as_of: date | None = None
    quality: str = "COMPLETE"
    trend: str | None = None  # IMPROVING / DETERIORATING / STABLE (Part 1B)
    peer_percentile: int | None = None  # 0-100 (Part 1B)


class AnalyticsEnvelope(BaseModel):
    """Standard analytics data payload per spec §14."""

    security_id: uuid.UUID
    security_name: str | None = None
    ticker: str | None = None
    metrics: dict[str, MetricValue] = {}


class AnalyticsMeta(BaseModel):
    """Response metadata."""

    request_id: str = ""
    engine: str = ""
    processing_time_ms: int = 0
    cache_hit: bool = False
    data_freshness: datetime | None = None


class AnalyticsResponse(BaseModel):
    """Top-level analytics API response."""

    data: AnalyticsEnvelope
    meta: AnalyticsMeta = AnalyticsMeta()


# ---------------------------------------------------------------------------
# Ratios (E1)
# ---------------------------------------------------------------------------

class RatiosByCategory(BaseModel):
    """All ratios for a security grouped by category."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    profitability: dict[str, float | None] = {}
    leverage: dict[str, float | None] = {}
    efficiency: dict[str, float | None] = {}
    growth: dict[str, float | None] = {}
    valuation: dict[str, float | None] = {}
    per_share: dict[str, float | None] = {}
    cash_flow: dict[str, float | None] = {}
    capital_allocation: dict[str, float | None] = {}
    dividend: dict[str, float | None] = {}


class RatioHistoryPoint(BaseModel):
    """Single point in a ratio time series."""

    period: str
    period_end_date: date | None = None
    value: float | None = None
    quality: str = "COMPLETE"


class RatioHistoryResponse(BaseModel):
    """Ratio time series for a security."""

    security_id: uuid.UUID
    metric_name: str
    metric_category: str
    data_points: list[RatioHistoryPoint] = []


# ---------------------------------------------------------------------------
# DuPont (E1)
# ---------------------------------------------------------------------------

class DuPontResponse(BaseModel):
    model_config = {"from_attributes": True}

    decomposition_id: uuid.UUID | None = None
    entity_id: uuid.UUID
    security_id: uuid.UUID | None = None
    period: str
    model_type: str
    roe: float | None = None
    net_profit_margin: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    tax_burden: float | None = None
    interest_burden: float | None = None
    operating_margin: float | None = None
    data_quality: str = "COMPLETE"


class DuPontHistoryResponse(BaseModel):
    """DuPont decomposition across multiple periods."""

    security_id: uuid.UUID
    entity_id: uuid.UUID
    decompositions: list[DuPontResponse] = []


# ---------------------------------------------------------------------------
# TTM (E1)
# ---------------------------------------------------------------------------

class TTMResponse(BaseModel):
    """Trailing twelve month financial metrics."""

    security_id: uuid.UUID
    entity_id: uuid.UUID
    as_of_date: date | None = None
    method: str = "SUM_4Q"
    quarters_used: int = 4
    data_quality: str = "COMPLETE"
    metrics: dict[str, float | None] = {}


# ---------------------------------------------------------------------------
# Multiples (E2)
# ---------------------------------------------------------------------------

class MultiplesResponse(BaseModel):
    """Current valuation multiples for a security."""

    security_id: uuid.UUID
    ticker: str | None = None
    as_of_date: date | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    multiples: dict[str, float | None] = {}


class MultipleHistoryPoint(BaseModel):
    calculation_date: date
    value: float | None = None


class MultipleHistoryResponse(BaseModel):
    security_id: uuid.UUID
    multiple_type: str
    data_points: list[MultipleHistoryPoint] = []


# ---------------------------------------------------------------------------
# WACC (E2)
# ---------------------------------------------------------------------------

class WACCResponse(BaseModel):
    model_config = {"from_attributes": True}

    wacc_id: uuid.UUID
    entity_id: uuid.UUID
    security_id: uuid.UUID | None = None
    calculation_date: date
    wacc: float | None = None
    cost_of_equity: float | None = None
    cost_of_debt_aftertax: float | None = None
    beta: float | None = None
    risk_free_rate: float | None = None
    equity_risk_premium: float | None = None
    debt_weight: float | None = None
    equity_weight: float | None = None
    market_cap: float | None = None
    total_debt: float | None = None
    data_quality: str = "COMPLETE"


class WACCComponentsResponse(BaseModel):
    """Detailed WACC component breakdown."""

    entity_id: uuid.UUID
    calculation_date: date
    risk_free_rate: float | None = None
    equity_risk_premium: float | None = None
    beta: float | None = None
    size_premium: float | None = None
    country_premium: float | None = None
    cost_of_equity: float | None = None
    cost_of_debt_pretax: float | None = None
    effective_tax_rate: float | None = None
    cost_of_debt_aftertax: float | None = None
    debt_weight: float | None = None
    equity_weight: float | None = None
    wacc: float | None = None
    market_cap: float | None = None
    total_debt: float | None = None


# ---------------------------------------------------------------------------
# Lineage / Audit (Spec §15)
# ---------------------------------------------------------------------------

class LineageInput(BaseModel):
    """Single input used in a calculation."""

    name: str
    source: str
    value: float | None = None
    period: str = ""
    filing_source: str = ""


class LineageResponse(BaseModel):
    model_config = {"from_attributes": True}

    lineage_id: uuid.UUID
    security_id: uuid.UUID
    engine_id: str
    engine_version: str
    output_metric: str
    output_value: float | None = None
    period: str
    calculation_formula: str | None = None
    inputs: list[dict] = []
    calculated_at: datetime


class LineageHistoryResponse(BaseModel):
    security_id: uuid.UUID
    metric_name: str
    entries: list[LineageResponse] = []


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class BulkRatioRequest(BaseModel):
    """Request ratios for multiple securities at once."""

    security_ids: list[uuid.UUID]
    metrics: list[str] | None = None  # None = all
    categories: list[str] | None = None  # None = all


# ---------------------------------------------------------------------------
# Trend Analysis (E1 — Part 1B)
# ---------------------------------------------------------------------------

class TrendMetric(BaseModel):
    """Trend analysis for a single ratio."""

    ratio_name: str
    current_value: float | None = None
    # Direction
    trend_1y: str | None = None  # IMPROVING / DETERIORATING / STABLE
    change_1y: float | None = None
    trend_3y: str | None = None
    change_3y: float | None = None
    trend_5y: str | None = None
    change_5y: float | None = None
    # Momentum
    momentum: float | None = None
    acceleration: float | None = None
    # Consistency
    std_5y: float | None = None
    cov_5y: float | None = None
    consistency: str | None = None  # HIGHLY_CONSISTENT / MODERATE / VOLATILE
    # Mean reversion
    zscore_5y: float | None = None
    mean_reversion_signal: str | None = None


class TrendResponse(BaseModel):
    """All trend metrics for a security."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    trends: list[TrendMetric] = []
    data_quality: str = "COMPLETE"


# ---------------------------------------------------------------------------
# Industry KPIs (E1 — Part 1B)
# ---------------------------------------------------------------------------

class IndustryKPIResponse(BaseModel):
    """Industry-specific KPIs for a security."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    gics_sector: str | None = None
    gics_industry: str | None = None
    kpi_set_applied: str | None = None
    kpis: dict[str, float | None] = {}
    data_quality: str = "COMPLETE"


# ---------------------------------------------------------------------------
# Peer Comparison (Part 1B)
# ---------------------------------------------------------------------------

class PeerMemberResponse(BaseModel):
    """Single peer in a peer group."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    name: str | None = None
    gics_sub_industry: str | None = None
    market_cap: float | None = None
    similarity_score: float = 0.0


class PeerGroupResponse(BaseModel):
    """Auto-generated or custom peer group."""

    subject_security_id: uuid.UUID
    subject_ticker: str | None = None
    method: str = "GICS_SUB_INDUSTRY"
    peer_count: int = 0
    peers: list[PeerMemberResponse] = []


class MetricComparisonResponse(BaseModel):
    """Single metric compared against peer group."""

    metric_name: str
    subject_value: float | None = None
    peer_mean: float | None = None
    peer_median: float | None = None
    peer_min: float | None = None
    peer_max: float | None = None
    peer_std: float | None = None
    percentile: int | None = None  # 0-100
    premium_discount: float | None = None  # vs median


class PeerComparisonResponse(BaseModel):
    """Full peer comparison for a security."""

    subject_security_id: uuid.UUID
    subject_ticker: str | None = None
    peer_count: int = 0
    as_of_date: date | None = None
    comparisons: list[MetricComparisonResponse] = []


class PercentileRankResponse(BaseModel):
    """Percentile ranks for a security across key metrics."""

    security_id: uuid.UUID
    ticker: str | None = None
    percentiles: dict[str, int] = {}  # metric_name → 0-100


# ---------------------------------------------------------------------------
# Quality & Scoring (E3)
# ---------------------------------------------------------------------------

class PiotroskiResponse(BaseModel):
    """Piotroski F-Score with full component breakdown."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    f_score: int | None = None  # 0-9
    zone: str | None = None  # STRONG / MODERATE / WEAK
    # Components (each 0 or 1)
    f1_positive_income: int | None = None
    f2_positive_ocf: int | None = None
    f3_improving_roa: int | None = None
    f4_earnings_quality: int | None = None
    f5_deleveraging: int | None = None
    f6_improving_liquidity: int | None = None
    f7_no_dilution: int | None = None
    f8_improving_gross_margin: int | None = None
    f9_improving_asset_turnover: int | None = None
    profitability_subscore: int | None = None  # 0-4
    data_quality: str = "COMPLETE"


class AltmanResponse(BaseModel):
    """Altman Z-Score with component breakdown."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    z_score: float | None = None
    zone: str | None = None  # SAFE / GREY / DISTRESS / NOT_APPLICABLE
    model: str | None = None  # ORIGINAL / NON_MANUFACTURING / NOT_APPLICABLE
    # Components
    x1_wc_ta: float | None = None
    x2_re_ta: float | None = None
    x3_ebit_ta: float | None = None
    x4_value: float | None = None  # MVE/TL or BVE/TL
    x4_description: str | None = None  # "MVE/TL" or "BVE/TL"
    x5_sales_ta: float | None = None  # original model only
    implied_pd: float | None = None
    gics_sector: str | None = None
    data_quality: str = "COMPLETE"


class BeneishResponse(BaseModel):
    """Beneish M-Score with component breakdown."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    m_score: float | None = None
    flag: str | None = None  # POSSIBLE_MANIPULATOR / UNLIKELY_MANIPULATOR
    # Components
    dsri: float | None = None
    gmi: float | None = None
    aqi: float | None = None
    sgi: float | None = None
    depi: float | None = None
    sgai: float | None = None
    tata: float | None = None
    lvgi: float | None = None
    components_available: int | None = None  # out of 8
    data_quality: str = "COMPLETE"


class AllScoresResponse(BaseModel):
    """All quality scores for a security."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    piotroski: PiotroskiResponse | None = None
    altman: AltmanResponse | None = None
    beneish: BeneishResponse | None = None
    data_quality: str = "COMPLETE"


class ScoreHistoryPoint(BaseModel):
    """Single historical score point."""

    period: str
    period_end_date: date | None = None
    score: float | None = None
    zone: str | None = None
    data_quality: str = "COMPLETE"


class ScoreHistoryResponse(BaseModel):
    """Score history for a specific scoring model."""

    security_id: uuid.UUID
    score_type: str  # piotroski / altman / beneish
    data_points: list[ScoreHistoryPoint] = []


# ---------------------------------------------------------------------------
# DCF Valuation (E2 — Part 2)
# ---------------------------------------------------------------------------

class DCFRequest(BaseModel):
    """Custom DCF assumptions (all optional — defaults computed from historicals)."""

    method: str = "FCFF"
    revenue_growth_rates: list[float] | None = None
    ebit_margins: list[float] | None = None
    tax_rate: float | None = None
    capex_pct_revenue: float | None = None
    wc_pct_revenue: float | None = None
    terminal_growth_rate: float = 0.025
    terminal_method: str = "GORDON_GROWTH"
    terminal_exit_multiple: float | None = None
    projection_years: int = 5
    wacc_override: float | None = None


class DCFProjectionYear(BaseModel):
    year: int
    revenue: float | None = None
    ebit: float | None = None
    nopat: float | None = None
    da: float | None = None
    capex: float | None = None
    wc_change: float | None = None
    fcf: float | None = None
    discount_factor: float | None = None
    pv: float | None = None


class DCFResponse(BaseModel):
    model_config = {"from_attributes": True}

    dcf_id: uuid.UUID
    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    calculation_date: date
    method: str
    enterprise_value: float | None = None
    equity_value: float | None = None
    implied_price: float | None = None
    current_price: float | None = None
    upside_downside_pct: float | None = None
    wacc_used: float | None = None
    terminal_value: float | None = None
    terminal_pct_of_ev: float | None = None
    terminal_method: str | None = None
    terminal_growth_rate: float | None = None
    pv_of_fcf: float | None = None
    pv_terminal: float | None = None
    projected_cashflows: list[dict] | None = None
    sensitivity_grid: dict | None = None
    assumptions: dict | None = None
    data_quality: str = "COMPLETE"


# ---------------------------------------------------------------------------
# Comparable Company Analysis (E2 — Part 2)
# ---------------------------------------------------------------------------

class CompsMultipleDetail(BaseModel):
    """Single multiple compared against peer group."""

    multiple_name: str
    subject_value: float | None = None
    peer_mean: float | None = None
    peer_median: float | None = None
    peer_min: float | None = None
    peer_max: float | None = None
    q1: float | None = None
    q3: float | None = None
    percentile: int | None = None
    implied_price: float | None = None
    premium_discount: float | None = None


class CompsResponse(BaseModel):
    model_config = {"from_attributes": True}

    comps_id: uuid.UUID
    security_id: uuid.UUID
    calculation_date: date
    peer_count: int | None = None
    peer_selection_method: str | None = None
    multiples_comparison: list[CompsMultipleDetail] | None = None
    composite_implied_price: float | None = None
    current_price: float | None = None
    upside_downside_pct: float | None = None
    data_quality: str = "COMPLETE"


# ---------------------------------------------------------------------------
# Football Field (E2 — Part 2)
# ---------------------------------------------------------------------------

class ValuationMethodRange(BaseModel):
    """Single methodology with low/mid/high range."""

    methodology: str
    low: float | None = None
    mid: float | None = None
    high: float | None = None
    confidence: str | None = None  # HIGH / MEDIUM / LOW


class FootballFieldResponse(BaseModel):
    """Combined valuation summary from all methodologies."""

    security_id: uuid.UUID
    ticker: str | None = None
    current_price: float | None = None
    methodologies: list[ValuationMethodRange] = []
    consensus_view: str | None = None  # UNDERVALUED / FAIRLY_VALUED / OVERVALUED


# ---------------------------------------------------------------------------
# Composite Quality Scores (E3 — Part 2)
# ---------------------------------------------------------------------------

class CompositeScoreComponent(BaseModel):
    """Single component in a composite score."""

    name: str
    raw_value: float | None = None
    score: float | None = None  # 0-100 or point value
    weight: float | None = None
    note: str | None = None


class CompositeScoreResponse(BaseModel):
    model_config = {"from_attributes": True}

    score_type: str
    score_value: float | None = None
    classification: str | None = None
    components: list[CompositeScoreComponent] = []
    data_quality: str = "COMPLETE"


class AllCompositeScoresResponse(BaseModel):
    """All composite scores for a security."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    as_of_date: date | None = None
    earnings_quality: CompositeScoreResponse | None = None
    financial_strength: CompositeScoreResponse | None = None
    dividend_safety: CompositeScoreResponse | None = None
    value_trap: CompositeScoreResponse | None = None
