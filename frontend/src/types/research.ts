// Mirrors src/schemas/company_primer_schema.py::CompanyPrimerResponse
// (GET /v4/research/primers/{entity_id}, served by
// src/api/routers/research_primers.py). The section content is a set of
// named dicts, not a generic `sections` list or a `company` sub-object --
// those never existed on this response.
export interface CompanyPrimer {
  id: string;
  entity_id: string;
  primer_version: number;
  generated_at?: string | null;
  executive_summary?: string | null;
  business_model?: {
    revenue_streams?: unknown;
    customer_segments?: unknown;
    geographic_exposure?: unknown;
    key_partnerships?: unknown;
  } | null;
  competitive_landscape?: {
    direct_competitors?: unknown;
    competitive_advantages?: unknown;
    market_position?: unknown;
  } | null;
  financial_health?: {
    revenue_ttm?: number | null;
    gross_margin?: number | null;
    operating_margin?: number | null;
    net_margin?: number | null;
    net_debt_to_ebitda?: number | null;
    fcf_margin?: number | null;
  } | null;
  strategic_initiatives?: {
    initiatives?: Array<{
      name: string;
      description?: string;
      timeline?: string;
      potential_impact?: string;
    }>;
  } | null;
  risk_factors?: {
    risks?: Array<{ category?: string; description: string; severity?: string }>;
  } | null;
  analyst_consensus?: Record<string, unknown> | null;
  recent_catalysts?: {
    catalysts?: Array<{ date?: string; event: string; strategic_significance?: string }>;
  } | null;
  data_completeness_score?: number | null;
  last_filing_date?: string | null;
  last_earnings_call_date?: string | null;
  ai_enabled: boolean;
  prompt_template_used?: string | null;
}

// Mirrors src/schemas/company_primer_schema.py::PrimerListResponse
// (GET /v4/research/primers/recent). There is no ticker/company-name field
// on this response -- callers needing a display name must resolve it
// separately (e.g. via the security/entity store).
export interface PrimerListSummary {
  entity_id: string;
  primer_version: number;
  generated_at?: string | null;
  executive_summary?: string | null;
  data_completeness_score?: number | null;
}

export interface MorningBriefing {
  id: string;
  briefing_date: string;
  narrative: string;
  portfolio_movers: Array<{ ticker: string; change_pct: number }>;
  macro_context: string;
}

export interface DetectedAnomaly {
  id: string;
  entity_id: string;
  anomaly_type: string;
  severity: number;
  narrative: string;
  detected_at: string;
}

// key_drivers/primary_risks/valuation_scenarios/catalysts are analyst-authored
// free-form JSON by design (see src/schemas/investment_thesis_schema.py::
// ThesisCreateRequest docstring) -- there is no enforced schema. The one
// documented (but not validated) convention is `{"items": [{...}]}`, where
// each item's only guaranteed key is the one named below (`driver`/`risk`/
// `description`); everything else is optional, caller-supplied metadata.
export interface ThesisDriverItem {
  driver: string;
  weight?: number;
  status?: string;
  current_impact?: string;
}

export interface ThesisRiskItem {
  risk: string;
  mitigation?: string;
  probability?: string;
  impact?: string;
  severity?: string;
}

export interface ThesisCatalystItem {
  description: string;
  event?: string;
  date?: string;
  timing?: string;
  expectedImpact?: string;
  notes?: string;
}

export interface ThesisValuationScenario {
  target_price: number;
  implied_return: number;
}

export interface ThesisValuationScenarios {
  current_price?: number;
  bull?: ThesisValuationScenario;
  base?: ThesisValuationScenario;
  bear?: ThesisValuationScenario;
}

// Mirrors src/schemas/investment_thesis_schema.py::ThesisResponse
// (GET /v4/research/thesis/{entity_id}/latest, served by
// src/api/routers/research_thesis.py). There is no nested `thesis` object,
// `ticker`, `direction`, or flat `drivers`/`risks`/`catalysts` array on this
// response -- key_drivers/primary_risks/catalysts are `{"items": [...]}`
// dicts following the convention above, and there is no `ticker`/`direction`
// field on the schema at all.
export interface InvestmentThesis {
  id: string;
  entity_id: string;
  analyst_id: string;
  version: number;
  thesis_title?: string | null;
  investment_horizon?: string | null;
  conviction_level?: string | null;
  executive_summary?: string | null;
  key_drivers?: { items?: ThesisDriverItem[] } | null;
  primary_risks?: { items?: ThesisRiskItem[] } | null;
  valuation_scenarios?: ThesisValuationScenarios | null;
  catalysts?: { items?: ThesisCatalystItem[] } | null;
  quality_metrics?: Record<string, unknown> | null;
  elevator_pitch?: string | null;
  slide_outline?: unknown;
  ai_enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface QASession {
  id: string;
  question: string;
  answer: string;
  confidence: number;
  data_sources: string[];
  created_at: string;
}

export interface MacroTheme {
  theme_name: string;
  score: number;
  description: string;
  affected_sectors: string[];
}

// Mirrors src/schemas/semantic_search_schema.py::SearchChunkResponse /
// SearchResultResponse (POST /v4/research/search, served by
// src/api/routers/research_search.py). Field names here are the real
// document-chunk fields (`chunk_text`, `relevance_score`, `publish_date`,
// `source_type`) -- not the page-local `snippet`/`relevance`/`date`/`source`
// display names a results list maps them into.
export interface SearchChunkResult {
  document_id: string;
  source_type: string;
  source_id?: string | null;
  title?: string | null;
  author?: string | null;
  publish_date?: string | null;
  entity_id?: string | null;
  chunk_index: number;
  chunk_text: string;
  relevance_score?: number | null;
}

export interface SearchResults {
  query: string;
  total_results: number;
  results: SearchChunkResult[];
  execution_time_ms?: number | null;
}

// Mirrors src/schemas/macro_themes_schema.py::ThemeScreenResponse
// (GET /v4/research/themes/{theme}/securities, served by
// src/api/routers/research_themes.py).
export interface ThemeScreenResult {
  entity_id: string;
  entity_name?: string | null;
  theme: string;
  exposure_score?: number | null;
  sensitivity_direction?: string | null;
  quantified_exposure?: string | null;
  as_of_date: string;
}
