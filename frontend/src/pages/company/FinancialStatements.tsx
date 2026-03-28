// ---------------------------------------------------------------------------
// Financial Statements — Income Statement, Balance Sheet, Cash Flow
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { PeriodSelector } from '@/components/financials/PeriodSelector';
import { CommonSizeToggle } from '@/components/financials/CommonSizeToggle';
import { StatementTable } from '@/components/financials/StatementTable';
import { LineItemChart } from '@/components/financials/LineItemChart';
import type { StatementRowData } from '@/components/financials/StatementTable';
import type { LineItemDataPoint } from '@/components/financials/LineItemChart';

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const ANNUAL_PERIODS = ['FY2025', 'FY2024', 'FY2023', 'FY2022'];
const QUARTERLY_PERIODS = ['Q1 2026', 'Q4 2025', 'Q3 2025', 'Q2 2025'];

const incomeStatementRows: StatementRowData[] = [
  {
    key: 'revenue',
    label: 'Revenue',
    indent: 0,
    isHeader: true,
    isBold: true,
    values: [391035, 383285, 383933, 394328],
    children: [
      { key: 'product-rev', label: 'Product Revenue', indent: 1, values: [295000, 289000, 291000, 297000] },
      { key: 'services-rev', label: 'Services Revenue', indent: 1, values: [96035, 94285, 92933, 97328] },
    ],
  },
  { key: 'cogs', label: 'Cost of Revenue', indent: 0, values: [214137, 210461, 214137, 223546] },
  {
    key: 'gross-profit',
    label: 'Gross Profit',
    indent: 0,
    isBold: true,
    values: [176898, 172824, 169796, 170782],
  },
  {
    key: 'opex',
    label: 'Operating Expenses',
    indent: 0,
    values: [56820, 54847, 53438, 51345],
    children: [
      { key: 'rnd', label: 'Research & Development', indent: 1, values: [30700, 29915, 29915, 26251] },
      { key: 'sga', label: 'Selling, General & Admin', indent: 1, values: [26120, 24932, 23523, 25094] },
    ],
  },
  { key: 'op-income', label: 'Operating Income', indent: 0, isBold: true, values: [120078, 117977, 114301, 119437] },
  { key: 'interest', label: 'Interest Expense', indent: 0, values: [-3600, -3750, -3933, -2931] },
  { key: 'other-inc', label: 'Other Income', indent: 0, values: [1800, 1200, 1543, -228] },
  { key: 'pretax', label: 'Pretax Income', indent: 0, isBold: true, values: [118278, 115427, 111911, 116278] },
  { key: 'tax', label: 'Income Tax Provision', indent: 0, values: [17178, 18432, 14948, 16474] },
  { key: 'net-income', label: 'Net Income', indent: 0, isBold: true, values: [101100, 96995, 96995, 99803] },
  { key: 'eps-basic', label: 'EPS (Basic)', indent: 0, values: [6.57, 6.16, 6.16, 6.15] },
  { key: 'eps-diluted', label: 'EPS (Diluted)', indent: 0, values: [6.52, 6.13, 6.13, 6.11] },
];

const balanceSheetRows: StatementRowData[] = [
  {
    key: 'current-assets',
    label: 'Current Assets',
    indent: 0,
    isHeader: true,
    isBold: true,
    values: [143566, 152987, 143566, 135405],
    children: [
      { key: 'cash', label: 'Cash & Equivalents', indent: 1, values: [29965, 29965, 29965, 23646] },
      { key: 'short-invest', label: 'Short-Term Investments', indent: 1, values: [31590, 37872, 31590, 24658] },
      { key: 'receivables', label: 'Accounts Receivable', indent: 1, values: [60932, 62027, 60932, 60932] },
      { key: 'inventory', label: 'Inventory', indent: 1, values: [6331, 6511, 6331, 4946] },
    ],
  },
  { key: 'total-assets', label: 'Total Assets', indent: 0, isBold: true, values: [352583, 364980, 352583, 352755] },
  {
    key: 'current-liab',
    label: 'Current Liabilities',
    indent: 0,
    isHeader: true,
    isBold: true,
    values: [145308, 153982, 145308, 153982],
    children: [
      { key: 'ap', label: 'Accounts Payable', indent: 1, values: [64115, 62611, 64115, 64115] },
      { key: 'deferred-rev', label: 'Deferred Revenue', indent: 1, values: [8061, 8031, 8061, 7912] },
      { key: 'st-debt', label: 'Short-Term Debt', indent: 1, values: [15828, 16999, 15828, 11128] },
    ],
  },
  { key: 'lt-debt', label: 'Long-Term Debt', indent: 0, values: [98959, 95281, 98959, 98959] },
  { key: 'total-liab', label: 'Total Liabilities', indent: 0, isBold: true, values: [278483, 291168, 290437, 302083] },
  { key: 'total-equity', label: 'Total Equity', indent: 0, isBold: true, values: [74100, 73812, 62146, 50672] },
];

const cashFlowRows: StatementRowData[] = [
  {
    key: 'op-cf',
    label: 'Operating Cash Flow',
    indent: 0,
    isBold: true,
    values: [118254, 110543, 110543, 122151],
    children: [
      { key: 'ni-cf', label: 'Net Income', indent: 1, values: [101100, 96995, 96995, 99803] },
      { key: 'da-cf', label: 'Depreciation & Amortization', indent: 1, values: [11519, 11104, 11104, 11104] },
      { key: 'sbc', label: 'Stock-Based Compensation', indent: 1, values: [10830, 10200, 10200, 9038] },
      { key: 'wc-change', label: 'Changes in Working Capital', indent: 1, values: [-5195, -7756, -7756, 2206] },
    ],
  },
  {
    key: 'inv-cf',
    label: 'Investing Cash Flow',
    indent: 0,
    isBold: true,
    values: [-8900, -8100, -8100, -22354],
    children: [
      { key: 'capex', label: 'Capital Expenditures', indent: 1, values: [-11000, -10959, -10959, -10708] },
      { key: 'invest-purch', label: 'Purchases of Investments', indent: 1, values: [-29000, -29513, -29513, -76923] },
      { key: 'invest-mat', label: 'Maturities of Investments', indent: 1, values: [31100, 32372, 32372, 65277] },
    ],
  },
  { key: 'fcf', label: 'Free Cash Flow', indent: 0, isBold: true, values: [107254, 99584, 99584, 111443] },
  { key: 'dividends', label: 'Dividends Paid', indent: 0, values: [-15200, -15025, -14841, -14841] },
  { key: 'buybacks', label: 'Share Buybacks', indent: 0, values: [-90100, -77550, -77550, -89402] },
];

const QUARTERLY_IS: StatementRowData[] = [
  { key: 'q-revenue', label: 'Revenue', indent: 0, isBold: true, values: [119500, 94930, 85777, 81797] },
  { key: 'q-cogs', label: 'Cost of Revenue', indent: 0, values: [64500, 51200, 46800, 44700] },
  { key: 'q-gp', label: 'Gross Profit', indent: 0, isBold: true, values: [55000, 43730, 38977, 37097] },
  { key: 'q-opex', label: 'Operating Expenses', indent: 0, values: [14800, 14200, 13700, 13600] },
  { key: 'q-op-inc', label: 'Operating Income', indent: 0, isBold: true, values: [40200, 29530, 25277, 23497] },
  { key: 'q-ni', label: 'Net Income', indent: 0, isBold: true, values: [33916, 24780, 22956, 21448] },
  { key: 'q-eps', label: 'EPS (Diluted)', indent: 0, values: [2.18, 1.64, 1.46, 1.40] },
];

const QUARTERLY_BS: StatementRowData[] = [
  { key: 'q-cash', label: 'Cash & Equivalents', indent: 0, values: [32500, 29965, 29500, 28200] },
  { key: 'q-ta', label: 'Total Assets', indent: 0, isBold: true, values: [358000, 352583, 348000, 345000] },
  { key: 'q-tl', label: 'Total Liabilities', indent: 0, isBold: true, values: [282000, 278483, 276000, 274000] },
  { key: 'q-te', label: 'Total Equity', indent: 0, isBold: true, values: [76000, 74100, 72000, 71000] },
];

const QUARTERLY_CF: StatementRowData[] = [
  { key: 'q-opcf', label: 'Operating CF', indent: 0, isBold: true, values: [35000, 28500, 27000, 26700] },
  { key: 'q-capex', label: 'Capital Expenditures', indent: 0, values: [-3000, -2800, -2700, -2600] },
  { key: 'q-fcf', label: 'Free Cash Flow', indent: 0, isBold: true, values: [32000, 25700, 24300, 24100] },
];

// --- Component ---------------------------------------------------------------

export default function FinancialStatements() {
  const [periodMode, setPeriodMode] = useState<'annual' | 'quarterly'>('annual');
  const [periodCount, setPeriodCount] = useState(4);
  const [commonSizeEnabled, setCommonSizeEnabled] = useState(false);

  // Line-item chart slide-over state
  const [chartOpen, setChartOpen] = useState(false);
  const [chartLabel, setChartLabel] = useState('');
  const [chartData, setChartData] = useState<LineItemDataPoint[]>([]);

  const isAnnual = periodMode === 'annual';
  const periods = isAnnual ? ANNUAL_PERIODS : QUARTERLY_PERIODS;
  const isRows = isAnnual ? incomeStatementRows : QUARTERLY_IS;
  const bsRows = isAnnual ? balanceSheetRows : QUARTERLY_BS;
  const cfRows = isAnnual ? cashFlowRows : QUARTERLY_CF;

  // Revenue base for common-size
  const revenueBase = isRows[0]?.values[0] ?? 1;

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
            rows={isRows}
            periods={periods}
            showCommonSize={commonSizeEnabled}
            commonSizeBase={revenueBase}
            onRowClick={handleRowClick}
          />
        </div>

        {/* Balance Sheet */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Balance Sheet ($M)</h2>
          <StatementTable
            rows={bsRows}
            periods={periods}
            onRowClick={handleRowClick}
          />
        </div>

        {/* Cash Flow Statement */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Cash Flow Statement ($M)</h2>
          <StatementTable
            rows={cfRows}
            periods={periods}
            onRowClick={handleRowClick}
          />
        </div>
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
