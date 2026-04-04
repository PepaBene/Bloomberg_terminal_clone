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

// --- Mock data (fallback when portfolio risk API is unavailable) ---------------

const MOCK_RISK_KPIS = [
  { label: 'Portfolio VaR (95%)', value: '$2.4M' },
  { label: 'Portfolio VaR (99%)', value: '$4.1M' },
  { label: 'CVaR (95%)', value: '$3.8M' },
  { label: 'Max Drawdown', value: '-8.2%' },
  { label: 'Sharpe Ratio', value: '1.42' },
  { label: 'Beta to S&P', value: '1.08' },
];

const MOCK_STRESS_TESTS = [
  { scenario: '2020 COVID Crash', portfolioReturn: -28.5, spReturn: -33.9, relative: 5.4 },
  { scenario: '2022 Rate Shock', portfolioReturn: -18.2, spReturn: -19.4, relative: 1.2 },
  { scenario: 'China Hard Landing', portfolioReturn: -22.8, spReturn: -25.0, relative: 2.2 },
  { scenario: 'Inflation Spike (+200bps)', portfolioReturn: -12.5, spReturn: -15.1, relative: 2.6 },
  { scenario: 'Credit Crisis (IG +150)', portfolioReturn: -15.8, spReturn: -20.2, relative: 4.4 },
];

const MOCK_FACTOR_EXPOSURE = [
  { factor: 'Market (Beta)', exposure: 1.08, contribution: 68.2 },
  { factor: 'Size (SMB)', exposure: -0.15, contribution: -3.2 },
  { factor: 'Value (HML)', exposure: -0.22, contribution: -5.8 },
  { factor: 'Momentum', exposure: 0.35, contribution: 12.4 },
  { factor: 'Quality', exposure: 0.42, contribution: 15.8 },
  { factor: 'Low Volatility', exposure: -0.18, contribution: -4.2 },
];

const MOCK_VAR_DECOMPOSITION = [
  { position: 'NVDA',  var95: 420 },
  { position: 'MSFT',  var95: 310 },
  { position: 'JPM',   var95: 280 },
  { position: 'META',  var95: 260 },
  { position: 'AAPL',  var95: 240 },
  { position: 'LLY',   var95: 220 },
  { position: 'V',     var95: 180 },
  { position: 'AMZN',  var95: 170 },
  { position: 'GOOGL', var95: 160 },
  { position: 'UNH',   var95: 150 },
];

const MOCK_SECTOR_CONCENTRATION = [
  { name: 'Technology', value: 38.2 },
  { name: 'Healthcare', value: 14.5 },
  { name: 'Financials', value: 12.8 },
  { name: 'Consumer Disc.', value: 10.4 },
  { name: 'Communication', value: 9.2 },
  { name: 'Industrials', value: 7.8 },
  { name: 'Other', value: 7.1 },
];

export default function RiskDashboard() {
  // [Bug 89 fix] — Source portfolioId from route params or store
  const { portfolioId: routePortfolioId } = useParams<{ portfolioId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const portfolioId = routePortfolioId ?? (primary as any)?.portfolio_id ?? 'default';

  // [Bug 89 fix] — Use proper portfolio risk hooks instead of security-level analytics hooks
  const { data: apiVaR } = useVaR(portfolioId, { enabled: !!portfolioId });
  const { data: apiStress } = useStressHistorical(portfolioId, { enabled: !!portfolioId });
  const { data: apiConcentration } = useConcentration(portfolioId, { enabled: !!portfolioId });
  const { data: apiFactors } = useRiskFactors(portfolioId, { enabled: !!portfolioId });

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
