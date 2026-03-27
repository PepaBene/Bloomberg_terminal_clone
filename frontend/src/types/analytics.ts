export interface FinancialRatio {
  ratio_name: string;
  category: string;
  value: number | null;
  period: string;
}

export interface CompositeScore {
  score_name: string;
  score_value: number;
  max_value: number;
  classification: string;
  components: Record<string, number>;
}

export interface DCFResult {
  fair_value: number;
  upside_pct: number;
  wacc: number;
  terminal_growth: number;
  sensitivity_matrix: number[][];
}

export interface PeerComparison {
  entity_id: string;
  entity_name: string;
  ticker: string;
  metrics: Record<string, number | null>;
}

export interface MultiplesHistory {
  period: string;
  pe_ratio: number | null;
  ev_ebitda: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
}
