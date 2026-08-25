// ---------------------------------------------------------------------------
// Risk Dashboard — VaR, Stress Tests, Factor Exposure
// [Bug 89-90 fix] — Replaced useCorrelation/useFactorExposure (security-level)
// with proper portfolio-level risk hooks from useRiskAnalytics.ts
// ---------------------------------------------------------------------------
import { useParams } from 'react-router-dom';
import { BarChartComponent, DonutChart } from '@/components/charts';
import { useVaR, useStressHistorical, useConcentration, useRiskFactors } from '@/api/hooks/useRiskAnalytics';
import { useSecurityStore } from '@/stores/securityContext';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// --- Empty fallbacks (P4-F-020) ----------------------------------------------
// We deliberately avoid hardcoded NVDA/MSFT/JPM VaR decompositions and
// fabricated stress-test P&L. Empty arrays render an empty panel; live
// data fills it.

const MOCK_RISK_KPIS = [
  { label: 'Portfolio VaR (95%)', value: '—' },
  { label: 'Portfolio VaR (99%)', value: '—' },
  { label: 'CVaR (95%)', value: '—' },
  { label: 'Max Drawdown', value: '—' },
  { label: 'Sharpe Ratio', value: '—' },
  { label: 'Beta to S&P', value: '—' },
];

const MOCK_STRESS_TESTS: { scenario: string; portfolioReturn: number; spReturn: number; relative: number }[] = [];

const MOCK_FACTOR_EXPOSURE: { factor: string; exposure: number; contribution: number }[] = [];

const MOCK_VAR_DECOMPOSITION: { position: string; var95: number }[] = [];

const MOCK_SECTOR_CONCENTRATION: { name: string; value: number }[] = [
  { name: 'Other', value: 0 },
];

export default function RiskDashboard() {
  // [Bug 89 fix] — Source portfolioId from route params or store
  // The 'default' string fallback used to be passed straight to the API as
  // if it were a real portfolio id -- with no portfolios created yet, that
  // 422s (not a valid UUID) on every load of this page. Leave it undefined
  // when there's no real portfolio so the queries stay disabled and the
  // panels render their honest empty state instead.
  const { portfolioId: routePortfolioId } = useParams<{ portfolioId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const portfolioId = routePortfolioId ?? (primary as any)?.portfolio_id ?? undefined;

  // [Bug 89 fix] — Use proper portfolio risk hooks instead of security-level analytics hooks
  const { data: apiVaR } = useVaR(portfolioId ?? '', { enabled: !!portfolioId });
  const { data: apiStress } = useStressHistorical(portfolioId ?? '', { enabled: !!portfolioId });
  const { data: apiConcentration } = useConcentration(portfolioId ?? '', { enabled: !!portfolioId });
  const { data: apiFactors } = useRiskFactors(portfolioId ?? '', { enabled: !!portfolioId });

  // Map API data with mock fallback
  const activeKPIs = (apiVaR as any)?.kpis ?? MOCK_RISK_KPIS;
  const activeStress = (apiStress as any)?.scenarios ?? (apiStress as any[]) ?? MOCK_STRESS_TESTS;
  const activeFactors = (apiFactors as any)?.factors ?? (apiFactors as any[]) ?? MOCK_FACTOR_EXPOSURE;
  const activeVarDecomp = (apiVaR as any)?.decomposition ?? MOCK_VAR_DECOMPOSITION;
  const activeSectorConc = (apiConcentration as any)?.sectors ?? (apiConcentration as any[]) ?? MOCK_SECTOR_CONCENTRATION;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Risk Dashboard</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Portfolio-level VaR, stress testing, and factor exposure analysis</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeKPIs.map((k: any) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      {/* VaR Decomposition + Sector Concentration Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>VaR Decomposition by Position ($K)</h2>
          <BarChartComponent
            data={activeVarDecomp}
            xKey="position"
            bars={[{ key: 'var95', color: '#E05252', name: 'VaR 95% ($K)' }]}
            height={250}
            yAxisFormat={(v: number) => `$${v}K`}
          />
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Concentration by Sector</h2>
          <DonutChart
            data={activeSectorConc}
            height={250}
            centerLabel="Sectors"
            centerValue={String(activeSectorConc.length)}
            showLegend
          />
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Stress Test Results</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Scenario', 'Portfolio', 'S&P 500', 'Relative'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Scenario' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeStress.map((s: any) => (
                <tr key={s.scenario} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.scenario}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)', fontWeight: 600 }}>{s.portfolioReturn.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{s.spReturn.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: s.relative > 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>+{s.relative.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Factor Exposure</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Factor', 'Exposure', 'Return Contribution %'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Factor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeFactors.map((f: any) => (
                <tr key={f.factor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.factor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{f.exposure >= 0 ? '+' : ''}{f.exposure.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.contribution >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{f.contribution >= 0 ? '+' : ''}{f.contribution.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
