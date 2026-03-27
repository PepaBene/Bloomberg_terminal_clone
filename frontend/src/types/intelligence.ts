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

export interface MoatAssessment {
  entity_id: string;
  moat_width: string;
  moat_score: number;
  sources: Record<string, number>;
}

export interface IndustryCycle {
  gics_code: string;
  cycle_position: string;
  confidence: number;
}
