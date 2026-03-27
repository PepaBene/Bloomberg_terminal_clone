export interface FinancialStatement {
  id: string;
  entity_id: string;
  fiscal_year: number;
  fiscal_quarter: number | null;
  period_type: string;
  filing_date: string;
  period_start: string;
  period_end: string;
  [key: string]: unknown; // Dynamic line items
}

export interface IncomeStatement extends FinancialStatement {
  revenue: number | null;
  cost_of_revenue: number | null;
  gross_profit: number | null;
  operating_expenses: number | null;
  operating_income: number | null;
  ebitda: number | null;
  net_income: number | null;
  eps_basic: number | null;
  eps_diluted: number | null;
}

export interface BalanceSheet extends FinancialStatement {
  total_assets: number | null;
  total_liabilities: number | null;
  total_equity: number | null;
  cash_and_equivalents: number | null;
  total_debt: number | null;
  current_assets: number | null;
  current_liabilities: number | null;
}

export interface CashFlowStatement extends FinancialStatement {
  operating_cash_flow: number | null;
  capital_expenditures: number | null;
  free_cash_flow: number | null;
  dividends_paid: number | null;
  share_repurchases: number | null;
}
