export interface FilingDiff {
  section_key: string;
  changes: Array<{
    type: string;
    content: string;
    classification: string;
  }>;
  materiality: string;
}

export interface EightKEvent {
  id: string;
  entity_id: string;
  filing_date: string;
  item_number: string;
  priority: number;
  title: string;
  summary: string;
  materiality: string;
}

export interface SentimentScore {
  entity_id: string;
  sentiment_score: number;
  sentiment_class: string;
  article_count: number;
  momentum: string;
}

export interface GovernanceAssessment {
  entity_id: string;
  governance_score: number;
  classification: string;
  red_flags: string[];
}

// Mirrors src/schemas/competitive_intelligence.py::MoatAssessmentResponse
// (GET /v3/competitive/{entity_id}/moat). Previously this interface only
// had a handful of made-up fields (`moat_width`/`moat_score`/`sources`)
// that didn't match the real response shape.
export interface MoatEvidenceEntry {
  source?: string;
  detail?: string;
  strength?: string;
}

export interface MoatAssessment {
  id: string;
  entity_id: string;
  as_of_date: string;
  moat_width: string;
  moat_stability?: string | null;
  moat_score?: number | null;
  roic_above_wacc_years?: number | null;
  roic_consistency_score?: number | null;
  gross_margin_stability?: number | null;
  gross_margin_10y_std?: number | null;
  market_share_trend?: string | null;
  market_share_5y_delta?: number | null;
  customer_retention_proxy?: number | null;
  cost_advantage_score?: number | null;
  network_effects_score?: number | null;
  switching_costs_score?: number | null;
  intangible_assets_score?: number | null;
  efficient_scale_score?: number | null;
  dominant_moat_source?: string | null;
  moat_evidence?: { evidence?: MoatEvidenceEntry[] } | null;
  ai_summary?: string | null;
  ai_enabled: boolean;
}

export interface IndustryCycle {
  gics_code: string;
  cycle_position: string;
  confidence: number;
}

// ---------------------------------------------------------------------------
// Company Intelligence (Pillar 3 Phase 2) — mirrors
// src/schemas/company_intelligence_p2.py
// ---------------------------------------------------------------------------

// GET .../intelligence -> CompanyIntelligenceResponse. The sub-objects are
// small ad-hoc summaries assembled by the router (see
// src/api/routers/company_intel_p2.py::get_company_intelligence), not full
// dumps of the underlying assessment tables -- there is no generic
// per-module score list (`modules`) on this response.
export interface CompanyIntelligenceOverview {
  entity_id: string;
  business_model?: {
    recurring_pct: number | null;
    moat_type: string | null;
    operating_leverage: number | null;
  } | null;
  capital_allocation?: {
    overall_score: number | null;
    roic_vs_wacc_spread: number | null;
  } | null;
  management_quality?: {
    execution_score: number | null;
    governance_score: number | null;
    overall_quality_score: number | null;
  } | null;
  balance_sheet_risk?: {
    net_debt_ebitda: number | null;
    refinancing_risk_score: number | null;
    z_score: number | null;
  } | null;
  governance_score?: number | null;
  ai_summary?: string | null;
}

// GET .../business-model -> BusinessModelResponse
export interface BusinessModelAnalysis {
  entity_id: string;
  revenue_quality?: {
    recurring_pct: number | null;
    customer_concentration: number | null;
    diversification_score: number | null;
    cyclicality_score: number | null;
    revenue_per_employee: number | null;
  } | null;
  // Raw dataclass asdict() of UnitEconomics -- revenue_per_employee,
  // revenue_per_subscriber, contribution_margin_by_segment.
  unit_economics?: Record<string, unknown> | null;
  scaling?: {
    operating_leverage: number | null;
    incremental_margin: number | null;
    sga_scalability: number | null;
  } | null;
  durability?: {
    moat_type: string | null;
    switching_cost_score: number | null;
    disruption_vulnerability: number | null;
  } | null;
  ai_summary?: string | null;
}

// GET .../capital-allocation -> CapitalAllocationResponse
export interface CapitalAllocationAssessment {
  entity_id: string;
  fcf_conversion?: number | null;
  // WorkingCapitalDiscipline dataclass asdict()
  working_capital?: {
    ccc: number | null;
    dio: number | null;
    dso: number | null;
    dpo: number | null;
    ccc_trend: string;
  } | null;
  roic_vs_wacc?: {
    spread: number | null;
    history: unknown;
  } | null;
  // MADiscipline dataclass asdict()
  ma_discipline?: {
    acquisition_count: number;
    serial_acquirer: boolean;
    goodwill_assets_ratio: number | null;
    goodwill_trend: string;
    impairment_count: number;
    post_acquisition_roic_impact: string;
  } | null;
  // BuybackEffectiveness dataclass asdict()
  buyback_effectiveness?: {
    shares_outstanding_trend: string;
    shares_5y_change_pct: number | null;
    avg_repurchase_price: number | null;
    current_price: number | null;
    repurchase_vs_current: string;
    buyback_yield: number | null;
  } | null;
  // DividendSustainability dataclass asdict()
  dividend_sustainability?: {
    eps_payout_ratio: number | null;
    fcf_payout_ratio: number | null;
    fcf_coverage: number | null;
    consecutive_growth_years: number | null;
    is_sustainable: boolean;
  } | null;
  overall_score?: number | null;
}

// GET .../management -> ManagementQualityResponse
export interface ManagementQualityAssessment {
  entity_id: string;
  execution_score?: number | null;
  governance_score?: number | null;
  accounting_flags?: Array<{ flag: string; severity: string }> | null;
  // CompensationAlignment dataclass asdict()
  compensation_alignment?: {
    pay_vs_tsr: string;
    pay_vs_revenue_growth: string;
    pay_vs_roic: string;
    ltip_pct: number | null;
    insider_ownership_pct: number | null;
    alignment_score: number;
  } | null;
  overall_score?: number | null;
  red_flags?: Array<Record<string, unknown>> | null;
}

// GET .../balance-sheet-risk -> BalanceSheetRiskResponse
export interface BalanceSheetRiskAssessment {
  entity_id: string;
  leverage?: {
    net_debt_ebitda: number | null;
    net_debt_ebitda_trend: string | null;
    interest_coverage: number | null;
    interest_coverage_trend: string | null;
  } | null;
  liquidity?: {
    liquidity_ratio: number | null;
    cash_burn_rate: number | null;
  } | null;
  refinancing_risk_score?: number | null;
  z_score?: number | null;
  // FIProfile dataclass asdict(), when the entity has FI issuance.
  fi_profile?: {
    total_outstanding: number | null;
    weighted_avg_ytm: number | null;
    weighted_avg_spread: number | null;
    fixed_pct: number | null;
    floating_pct: number | null;
    is_investment_grade: boolean | null;
    credit_rating: string | null;
  } | null;
  ai_summary?: string | null;
}

// ---------------------------------------------------------------------------
// Revenue drivers / cost structure / margin analysis / SWOT / Porter's Five
// Forces: COMPANY_INTEL.revenueDrivers/costStructure/marginAnalysis and
// COMPETITIVE.swot/porterForces (frontend/src/api/endpoints.ts) do not
// correspond to any implemented backend route or Pydantic schema today (no
// `/revenue-drivers`, `/cost-structure`, `/margin-analysis`, `/swot`, or
// `/porter-forces` endpoint exists in src/api/routers/*). These hooks will
// error until that backend work lands. The shapes below document only what
// the frontend already expects to render, not a verified backend contract.
export interface RevenueDriversResponse {
  entity_id?: string;
  drivers?: Array<{
    driver: string;
    impact?: string;
    trend?: string;
    contribution?: number;
  }>;
}

export interface CostStructureResponse {
  entity_id?: string;
  items?: Array<{
    category: string;
    pctRevenue?: number;
    trend?: string;
  }>;
}

export interface MarginAnalysisResponse {
  entity_id?: string;
  margins?: Array<{
    metric: string;
    current?: number;
    prior?: number;
    fiveYrAvg?: number;
  }>;
}

export interface SWOTAssessment {
  entity_id?: string;
  strengths?: string[];
  weaknesses?: string[];
  opportunities?: string[];
  threats?: string[];
}

export interface PorterForcesResponse {
  entity_id?: string;
  forces?: Array<{
    name: string;
    score: number;
    level: string;
  }>;
}
