export interface Portfolio {
  id: string;
  user_id: string;
  portfolio_name: string;
  portfolio_type: string;
  benchmark_id: string | null;
  inception_date: string;
  base_currency: string;
  initial_cash: number;
  current_cash: number;
  status: string;
}

export interface Position {
  id: string;
  portfolio_id: string;
  security_id: string | null;
  ticker: string;
  shares: number;
  cost_basis_total: number;
  cost_basis_per_share: number;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  weight: number | null;
  status: string;
}

export interface Transaction {
  id: string;
  portfolio_id: string;
  ticker: string;
  transaction_type: string;
  transaction_date: string;
  shares: number;
  price_per_share: number;
  gross_amount: number;
  commission: number;
  net_amount: number;
}

export interface NAVSnapshot {
  snapshot_date: string;
  total_market_value: number;
  cash: number;
  total_nav: number;
  daily_return_pct: number | null;
  cumulative_return_pct: number | null;
}
