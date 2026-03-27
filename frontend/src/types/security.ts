export interface Security {
  security_id: string;
  ticker: string;
  figi: string | null;
  name: string;
  asset_class: string;
  exchange: string | null;
  currency: string | null;
  entity_id: string | null;
  status: string;
  gics_sector: string | null;
  gics_industry: string | null;
  market_cap: number | null;
}

export interface SecuritySearchResult {
  security_id: string;
  ticker: string;
  name: string;
  asset_class: string;
  exchange: string | null;
  score: number;
}

export interface SecurityPrice {
  price_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  adj_close: number | null;
  volume: number | null;
}
