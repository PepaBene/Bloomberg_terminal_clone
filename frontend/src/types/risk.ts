export interface VaRResult {
  confidence_level: number;
  holding_period_days: number;
  portfolio_var: number;
  undiversified_var: number;
  diversification_benefit: number;
  component_var: Record<string, number>;
}

export interface StressTestResult {
  scenario_name: string;
  portfolio_pnl: number;
  portfolio_pnl_pct: number;
  position_impacts: Array<{
    ticker: string;
    pnl: number;
    pnl_pct: number;
  }>;
}

export interface FactorExposure {
  factor_name: string;
  exposure: number;
  benchmark_exposure: number;
  active_exposure: number;
  contribution: number;
}

export interface ComplianceResult {
  rule_id: string;
  rule_name: string;
  status: string;
  current_value: number;
  limit_value: number;
  severity: string;
}
