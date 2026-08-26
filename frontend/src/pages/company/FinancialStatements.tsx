// ---------------------------------------------------------------------------
// Financial Statements — Income Statement, Balance Sheet, Cash Flow
// ---------------------------------------------------------------------------
import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useIncomeStatements, useBalanceSheets, useCashFlows, useSegments, useRevenueBreakdown, useEntity } from '@/hooks';
import { PeriodSelector } from '@/components/financials/PeriodSelector';
import { CommonSizeToggle } from '@/components/financials/CommonSizeToggle';
import { StatementTable } from '@/components/financials/StatementTable';
import { LineItemChart } from '@/components/financials/LineItemChart';
import type { StatementRowData } from '@/components/financials/StatementTable';
import type { LineItemDataPoint } from '@/components/financials/LineItemChart';

// --- API response shapes (subset of backend schemas actually read) ---------
// Mirrors `SegmentDataResponse` (src/schemas/fundamentals.py:226) wrapped in
// `PaginatedResponse` (src/schemas/common.py:52) — `GET /v1/entities/{id}/segments`
// returns `{data: [...], meta: {...}}`, not a bare array.

interface SegmentDataApi {
  segment_name: string;
  revenue: number | null;
  operating_income: number | null;
  operating_margin: number | null;
}

interface PaginatedSegmentsApi {
  data?: SegmentDataApi[];
}

// Mirrors the fields we read from `EntityResponse` (src/schemas/entity.py:32).
interface EntityDetailApi {
  legal_name?: string | null;
  short_name?: string | null;
}

// Real shape of GET /v1/entities/{id}/fundamentals/{income-statement,
// balance-sheet,cash-flow} (src/schemas/fundamentals.py) -- a flat,
// period-major PaginatedResponse (`{data: [...]}`), one row per period with
// every line item as a field on that row, ordered newest-first. This is NOT
// the `{annual: [...], quarterly: [...]}` line-item-major shape the page
// previously assumed (which never existed on the wire), so every table
// rendered zero rows regardless of how much real data existed. Pivoted into
// `StatementRowData[]` (one row per line item, one column per period) below.
interface StatementPeriodRow {
  period_end_date: string | null;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  period_type: string | null;
  [key: string]: unknown;
}
interface StatementsApi {
  data?: StatementPeriodRow[];
}

interface LineItemDef {
  key: string;
  label: string;
  indent?: number;
  isBold?: boolean;
}

const INCOME_STATEMENT_LINE_ITEMS: LineItemDef[] = [
  { key: 'total_revenue', label: 'Total Revenue', isBold: true },
  { key: 'cost_of_revenue', label: 'Cost of Revenue', indent: 1 },
  { key: 'gross_profit', label: 'Gross Profit', isBold: true },
  { key: 'research_development', label: 'R&D', indent: 1 },
  { key: 'selling_general_admin', label: 'SG&A', indent: 1 },
  { key: 'total_operating_expense', label: 'Total Operating Expense', indent: 1 },
  { key: 'operating_income', label: 'Operating Income', isBold: true },
  { key: 'other_income_expense', label: 'Other Income/Expense', indent: 1 },
  { key: 'pretax_income', label: 'Pretax Income' },
  { key: 'income_tax_expense', label: 'Income Tax Expense', indent: 1 },
  { key: 'net_income', label: 'Net Income', isBold: true },
  { key: 'basic_eps', label: 'Basic EPS' },
  { key: 'diluted_eps', label: 'Diluted EPS' },
];

const BALANCE_SHEET_LINE_ITEMS: LineItemDef[] = [
  { key: 'cash_and_equivalents', label: 'Cash & Equivalents', indent: 1 },
  { key: 'accounts_receivable', label: 'Accounts Receivable', indent: 1 },
  { key: 'inventory', label: 'Inventory', indent: 1 },
  { key: 'total_current_assets', label: 'Total Current Assets', isBold: true },
  { key: 'ppe_net', label: 'PP&E, Net', indent: 1 },
  { key: 'goodwill', label: 'Goodwill', indent: 1 },
  { key: 'total_non_current_assets', label: 'Total Non-Current Assets', isBold: true },
  { key: 'total_assets', label: 'Total Assets', isBold: true },
  { key: 'accounts_payable', label: 'Accounts Payable', indent: 1 },
  { key: 'short_term_debt', label: 'Short-Term Debt', indent: 1 },
  { key: 'total_current_liabilities', label: 'Total Current Liabilities', isBold: true },
  { key: 'long_term_debt', label: 'Long-Term Debt', indent: 1 },
  { key: 'total_nc_liabilities', label: 'Total Non-Current Liabilities', isBold: true },
  { key: 'total_liabilities', label: 'Total Liabilities', isBold: true },
  { key: 'total_equity', label: 'Total Equity', isBold: true },
  { key: 'total_debt', label: 'Total Debt' },
  { key: 'net_debt', label: 'Net Debt' },
];

const CASH_FLOW_LINE_ITEMS: LineItemDef[] = [
  { key: 'net_income', label: 'Net Income' },
  { key: 'depreciation_amortization', label: 'D&A', indent: 1 },
  { key: 'stock_based_comp', label: 'Stock-Based Comp', indent: 1 },
  { key: 'change_in_receivables', label: 'Change in Receivables', indent: 1 },
  { key: 'change_in_inventory', label: 'Change in Inventory', indent: 1 },
  { key: 'change_in_payables', label: 'Change in Payables', indent: 1 },
  { key: 'cash_from_operations', label: 'Cash From Operations', isBold: true },
  { key: 'capital_expenditures', label: 'Capital Expenditures', indent: 1 },
  { key: 'acquisitions', label: 'Acquisitions', indent: 1 },
  { key: 'cash_from_investing', label: 'Cash From Investing', isBold: true },
  { key: 'debt_issued', label: 'Debt Issued', indent: 1 },
  { key: 'debt_repaid', label: 'Debt Repaid', indent: 1 },
  { key: 'stock_repurchased', label: 'Stock Repurchased', indent: 1 },
  { key: 'dividends_paid', label: 'Dividends Paid', indent: 1 },
  { key: 'cash_from_financing', label: 'Cash From Financing', isBold: true },
  { key: 'net_change_in_cash', label: 'Net Change in Cash', isBold: true },
  { key: 'free_cash_flow', label: 'Free Cash Flow', isBold: true },
];

function periodLabel(p: StatementPeriodRow): string {
  if (p.fiscal_quarter != null) return `Q${p.fiscal_quarter} FY${p.fiscal_year}`;
  if (p.fiscal_year != null) return `FY${p.fiscal_year}`;
  return p.period_end_date ?? '—';
}

function toMillions(v: unknown): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n / 1_000_000 : null;
}

function pivotStatements(
  rows: StatementPeriodRow[] | undefined,
  lineItems: LineItemDef[],
  periodCount: number,
): { periods: string[]; rows: StatementRowData[] } {
  const slice = (rows ?? []).slice(0, periodCount);
  const periods = slice.map(periodLabel);
  const pivoted: StatementRowData[] = lineItems.map((item) => ({
    key: item.key,
    label: item.label,
    indent: item.indent ?? 0,
    isBold: item.isBold,
    values: slice.map((p) =>
      item.key === 'basic_eps' || item.key === 'diluted_eps'
        ? (p[item.key] != null ? Number(p[item.key]) : null)
        : toMillions(p[item.key]),
    ),
  }));
  return { periods, rows: pivoted };
}

const DEFAULT_COMPANY = { name: 'Loading...', ticker: '' };

// --- Component ---------------------------------------------------------------

export default function FinancialStatements() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // [P1-FP-006 fix] — Wire the header to the real current entity instead of a
  // static "Loading..." constant. `Security` (the store's `primary`) already
  // carries `name`/`ticker` directly; fall back to `useEntity`'s
  // `legal_name`/`short_name` (no ticker on Entity) when the store hasn't been
  // populated yet (e.g. direct navigation via the `entityId` route param).
  const { data: apiEntity } = useEntity(resolvedId ?? '', { enabled: !!resolvedId && !primary }) as {
    data: EntityDetailApi | undefined;
  };
  const company = {
    name: primary?.name ?? apiEntity?.short_name ?? apiEntity?.legal_name ?? DEFAULT_COMPANY.name,
    ticker: primary?.ticker ?? DEFAULT_COMPANY.ticker,
  };

  const [periodMode, setPeriodMode] = useState<'annual' | 'quarterly'>('annual');
  const [periodCount, setPeriodCount] = useState(4);
  const [commonSizeEnabled, setCommonSizeEnabled] = useState(false);
  const isAnnual = periodMode === 'annual';
  const periodTypeParam = isAnnual ? 'ANNUAL' : 'QUARTERLY';

  // Wire to API hooks
  // (`resolvedId` is `string | undefined`; these hooks take a required
  // `string` and internally guard on `enabled: !!entityId`, so passing `?? ''`
  // is safe — it never fires a request when there's no resolved id.)
  const { data: apiIncome } = useIncomeStatements(resolvedId ?? '', { period_type: periodTypeParam, page_size: 20 }) as { data: StatementsApi | undefined };
  const { data: apiBalance } = useBalanceSheets(resolvedId ?? '', { period_type: periodTypeParam, page_size: 20 }) as { data: StatementsApi | undefined };
  const { data: apiCashFlow } = useCashFlows(resolvedId ?? '', { period_type: periodTypeParam, page_size: 20 }) as { data: StatementsApi | undefined };
  const { data: apiSegments } = useSegments(resolvedId ?? '') as { data: PaginatedSegmentsApi | undefined };
  const { data: apiRevBreakdown } = useRevenueBreakdown(resolvedId ?? '') as { data: PaginatedSegmentsApi | undefined };

  // Line-item chart slide-over state
  const [chartOpen, setChartOpen] = useState(false);
  const [chartLabel, setChartLabel] = useState('');
  const [chartData, setChartData] = useState<LineItemDataPoint[]>([]);

  // Pivot the real period-major API rows (one row per period, every line
  // item as a field) into line-item-major StatementRowData[] (one row per
  // line item, one column per period) -- see the StatementsApi comment above
  // for why this couldn't just read `.annual`/`.quarterly` off the response.
  const income = useMemo(
    () => pivotStatements(apiIncome?.data, INCOME_STATEMENT_LINE_ITEMS, periodCount),
    [apiIncome, periodCount],
  );
  const balance = useMemo(
    () => pivotStatements(apiBalance?.data, BALANCE_SHEET_LINE_ITEMS, periodCount),
    [apiBalance, periodCount],
  );
  const cashFlow = useMemo(
    () => pivotStatements(apiCashFlow?.data, CASH_FLOW_LINE_ITEMS, periodCount),
    [apiCashFlow, periodCount],
  );

  const periods = income.periods.length > 0 ? income.periods : balance.periods;
  const incomeRows = income.rows;
  const balanceRows = balance.rows;
  const cashFlowDisplayRows = cashFlow.rows;

  // Revenue base for common-size
  const revenueBase = incomeRows[0]?.values[0] ?? 1;

  const segmentRows: SegmentDataApi[] = useMemo(
    () => (Array.isArray(apiSegments?.data) ? apiSegments!.data! : []),
    [apiSegments],
  );

  const revenueBreakdownRows: (SegmentDataApi & { pctOfTotal: number | null })[] = useMemo(() => {
    const rows = Array.isArray(apiRevBreakdown?.data) ? apiRevBreakdown!.data! : [];
    const total = rows.reduce((sum, r) => sum + (r.revenue ?? 0), 0);
    return rows.map((r) => ({
      ...r,
      pctOfTotal: total > 0 && r.revenue != null ? (r.revenue / total) * 100 : null,
    }));
  }, [apiRevBreakdown]);

  const handleRowClick = useCallback(
    (row: StatementRowData) => {
      if (row.isHeader) return;
      const data: LineItemDataPoint[] = periods.map((p, i) => ({
        period: p,
        value: row.values[i] ?? 0,
      }));
      setChartLabel(row.label);
      setChartData(data);
      setChartOpen(true);
    },
    [periods],
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      {/* Header row with title, period selector, and common-size toggle */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Financial Statements
        </h1>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
          {company.ticker} &mdash; {company.name}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <CommonSizeToggle enabled={commonSizeEnabled} onChange={setCommonSizeEnabled} />
          <PeriodSelector
            mode={periodMode}
            onModeChange={setPeriodMode}
            periodCount={periodCount}
            onPeriodCountChange={setPeriodCount}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {/* Income Statement */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Income Statement ($M)</h2>
          <StatementTable
            rows={incomeRows}
            periods={periods}
            showCommonSize={commonSizeEnabled}
            commonSizeBase={revenueBase}
            onRowClick={handleRowClick}
            anomalyThreshold={0.3}
          />
        </div>

        {/* Balance Sheet */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Balance Sheet ($M)</h2>
          <StatementTable
            rows={balanceRows}
            periods={periods}
            onRowClick={handleRowClick}
            anomalyThreshold={0.3}
          />
        </div>

        {/* Cash Flow Statement */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Cash Flow Statement ($M)</h2>
          <StatementTable
            rows={cashFlowDisplayRows}
            periods={periods}
            onRowClick={handleRowClick}
            anomalyThreshold={0.3}
          />
        </div>

        {/* Segments */}
        {/* [P1-FP-008 fix] `GET /v1/entities/{id}/segments` returns a
            `PaginatedResponse` (`{data: [...], meta}`), and each row is a
            `SegmentDataResponse` with snake_case fields (`segment_name`,
            `operating_income`, `operating_margin`), not the camelCase
            `{name, operatingIncome, margin}` shape this used to assume. */}
        {segmentRows.length > 0 && (
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Business Segments</h2>
            <table className="terminal-table">
              <thead><tr><th>Segment</th><th className="right">Revenue ($M)</th><th className="right">Operating Income ($M)</th><th className="right">Margin</th></tr></thead>
              <tbody>
                {segmentRows.map((s) => (
                  <tr key={s.segment_name}>
                    <td style={{ fontWeight: 500 }}>{s.segment_name}</td>
                    <td className="right">{s.revenue?.toLocaleString() ?? '—'}</td>
                    <td className="right">{s.operating_income?.toLocaleString() ?? '—'}</td>
                    <td className="right">{s.operating_margin != null ? `${(s.operating_margin * 100).toFixed(1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Revenue Breakdown */}
        {/* [P1-FP-008 fix] Same `SegmentDataResponse`/`PaginatedResponse` shape
            as segments above (this hook hits the same `/segments` endpoint
            filtered to `segment_type=PRODUCT`). The backend has no
            `pctOfTotal`/`growth` fields, so % of total is computed client-side
            from the fetched rows and YoY growth (not available) shows '—'. */}
        {revenueBreakdownRows.length > 0 && (
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Revenue Breakdown</h2>
            <table className="terminal-table">
              <thead><tr><th>Category</th><th className="right">Revenue ($M)</th><th className="right">% of Total</th><th className="right">YoY Growth</th></tr></thead>
              <tbody>
                {revenueBreakdownRows.map((r) => (
                  <tr key={r.segment_name}>
                    <td style={{ fontWeight: 500 }}>{r.segment_name}</td>
                    <td className="right">{r.revenue?.toLocaleString() ?? '—'}</td>
                    <td className="right">{r.pctOfTotal != null ? `${r.pctOfTotal.toFixed(1)}%` : '—'}</td>
                    <td className="right">—</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Line Item Chart Slide-over */}
      {chartOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            width: '420px',
            zIndex: 1000,
            background: 'var(--color-surface-raised)',
            borderLeft: '1px solid var(--color-surface-border)',
            boxShadow: 'var(--shadow-float)',
            display: 'flex',
            flexDirection: 'column',
            animation: 'slideInLeft 200ms ease-out both',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: '1px solid var(--color-surface-border)',
            }}
          >
            <h3 style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-lg)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              margin: 0,
            }}>
              {chartLabel}
            </h3>
            <button
              type="button"
              onClick={() => setChartOpen(false)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-text-secondary)',
                cursor: 'pointer',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-lg)',
                padding: '4px 8px',
              }}
            >
              &#10005;
            </button>
          </div>
          <div style={{ flex: 1, padding: '16px', overflow: 'auto' }}>
            <LineItemChart
              label={chartLabel}
              data={chartData}
              format="currency"
            />
          </div>
        </div>
      )}
    </div>
  );
}
