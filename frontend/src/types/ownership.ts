export interface InstitutionalHolding {
  institution_name: string;
  institution_type: string;
  shares: number;
  market_value: number;
  portfolio_pct: number;
  change_shares: number;
  change_pct: number;
  filing_date: string;
}

export interface ShortInterest {
  report_date: string;
  short_interest: number;
  days_to_cover: number;
  short_pct_float: number;
  short_pct_outstanding: number;
}

export interface InsiderTransaction {
  person_name: string;
  title: string;
  transaction_type: string;
  shares: number;
  price: number;
  total_value: number;
  transaction_date: string;
}
