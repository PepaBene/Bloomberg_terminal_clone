// ---------------------------------------------------------------------------
// Financial Statements — Income Statement, Balance Sheet, Cash Flow
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useIncomeStatements, useBalanceSheets, useCashFlows, useSegments, useRevenueBreakdown } from '@/hooks';
import { PeriodSelector } from '@/components/financials/PeriodSelector';
import { CommonSizeToggle } from '@/components/financials/CommonSizeToggle';
import { StatementTable } from '@/components/financials/StatementTable';
import { LineItemChart } from '@/components/financials/LineItemChart';
import type { StatementRowData } from '@/components/financials/StatementTable';
import type { LineItemDataPoint } from '@/components/financials/LineItemChart';

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Loading...', ticker: '' };

const ANNUAL_PERIODS = ['FY2025', 'FY2024', 'FY2023', 'FY2022'];
const QUARTERLY_PERIODS = ['Q1 2026', 'Q4 2025', 'Q3 2025', 'Q2 2025'];

const incomeStatementRows: StatementRowData[] = [];

const balanceSheetRows: StatementRowData[] = [];

const cashFlowRows: StatementRowData[] = [];

const QUARTERLY_IS: StatementRowData[] = [];

const QUARTERLY_BS: StatementRowData[] = [];

const QUARTERLY_CF: StatementRowData[] = [];

// --- Component ---------------------------------------------------------------

export default function FinancialStatements() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // Wire to API hooks
  const { data: apiIncome } = useIncomeStatements(resolvedId);
  const { data: apiBalance } = useBalanceSheets(resolvedId);
  const { data: apiCashFlow } = useCashFlows(resolvedId);
  const { data: apiSegments } = useSegments(resolvedId);
  const { data: apiRevBreakdown } = useRevenueBreakdown(resolvedId);

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

  // Use API data if available, fall back to mock
  const incomeRows = (isAnnual ? apiIncome?.annual : apiIncome?.quarterly) ?? isRows;
  const balanceRows = (isAnnual ? apiBalance?.annual : apiBalance?.quarterly) ?? bsRows;
  const cashFlowDisplayRows = (isAnnual ? apiCashFlow?.annual : apiCashFlow?.quarterly) ?? cfRows;

  // Revenue base for common-size
  const revenueBase = incomeRows[0]?.values[0] ?? 1;

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
        {(apiSegments ?? []).length > 0 && (
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Business Segments</h2>
            <table className="terminal-table">
              <thead><tr><th>Segment</th><th className="right">Revenue ($M)</th><th className="right">Operating Income ($M)</th><th className="right">Margin</th></tr></thead>
              <tbody>
                {(apiSegments as any[]).map((s: any) => (
                  <tr key={s.name}>
                    <td style={{ fontWeight: 500 }}>{s.name}</td>
                    <td className="right">{s.revenue?.toLocaleString() ?? '—'}</td>
                    <td className="right">{s.operatingIncome?.toLocaleString() ?? '—'}</td>
                    <td className="right">{s.margin != null ? `${(s.margin * 100).toFixed(1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Revenue Breakdown */}
        {(apiRevBreakdown ?? []).length > 0 && (
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Revenue Breakdown</h2>
            <table className="terminal-table">
              <thead><tr><th>Category</th><th className="right">Revenue ($M)</th><th className="right">% of Total</th><th className="right">YoY Growth</th></tr></thead>
              <tbody>
                {(apiRevBreakdown as any[]).map((r: any) => (
                  <tr key={r.category}>
                    <td style={{ fontWeight: 500 }}>{r.category}</td>
                    <td className="right">{r.revenue?.toLocaleString() ?? '—'}</td>
                    <td className="right">{r.pctOfTotal != null ? `${r.pctOfTotal.toFixed(1)}%` : '—'}</td>
                    <td className="right" style={{ color: (r.growth ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                      {r.growth != null ? `${r.growth >= 0 ? '+' : ''}${r.growth.toFixed(1)}%` : '—'}
                    </td>
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
