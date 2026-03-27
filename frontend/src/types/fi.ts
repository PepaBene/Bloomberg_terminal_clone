export interface Bond {
  bond_id: string;
  cusip: string;
  issuer_name: string;
  coupon_rate: number;
  maturity_date: string;
  bond_type: string;
  seniority: string;
  is_callable: boolean;
  rating: string | null;
  oas_bps: number | null;
  ytw: number | null;
  modified_duration: number | null;
}

export interface TreasuryYield {
  yield_date: string;
  y_1m: number | null;
  y_3m: number | null;
  y_6m: number | null;
  y_1y: number | null;
  y_2y: number | null;
  y_5y: number | null;
  y_10y: number | null;
  y_30y: number | null;
  spread_2s10s: number | null;
  spread_3m10y: number | null;
}

export interface CreditRating {
  agency: string;
  rating: string;
  outlook: string | null;
  on_watch: string | null;
  effective_date: string;
  is_investment_grade: boolean;
}

export interface CreditSpreadIndex {
  index_date: string;
  index_code: string;
  oas: number;
  yield_value: number;
  duration: number;
}
