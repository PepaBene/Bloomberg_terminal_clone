export interface CompanyPrimer {
  id: string;
  entity_id: string;
  primer_text: string;
  data_completeness: number;
  generated_at: string;
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

export interface InvestmentThesis {
  id: string;
  entity_id: string;
  conviction_level: string;
  key_drivers: string[];
  primary_risks: string[];
  elevator_pitch: string;
  created_at: string;
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
