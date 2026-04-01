// ---------------------------------------------------------------------------
// Risk Page — Portfolio VaR, Concentration, Stress Tests, Factor Exposure,
// Correlation, Drift Monitoring, Custom Stress Tests
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  usePortfolioVaR,
  usePortfolioCVaR,
  usePortfolioConcentration,
  usePortfolioStressHistorical,
  usePortfolioCompliance,
  usePortfolioFactorExposure,
  usePortfolioCorrelation,
  usePortfolioDrift,
} from '@/hooks';
import { api } from '@/api/client';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const mockRiskKPIs = [
  { label: '1D VaR (95%)', value: '$385K' },
  { label: '1D VaR (99%)', value: '$620K' },
  { label: '10D VaR (95%)', value: '$1.22M' },
  { label: 'CVaR (95%)', value: '$580K' },
  { label: 'Tracking Error', value: '2.8%' },
  { label: 'Active Share', value: '42.5%' },
];

const mockConcentrationRisk = [
  { name: 'Top 1 Holding', weight: 8.2, ticker: 'NVDA', varContribution: 18.5 },
  { name: 'Top 5 Holdings', weight: 32.8, ticker: 'Various', varContribution: 52.1 },
  { name: 'Top 10 Holdings', weight: 55.2, ticker: 'Various', varContribution: 72.8 },
  { name: 'Top Sector (Tech)', weight: 38.5, ticker: 'XLK', varContribution: 45.2 },
  { name: 'Top Country (US)', weight: 82.3, ticker: 'US', varContribution: 78.5 },
];

const mockStressResults = [
  { scenario: 'Equity -20%', portfolioPnL: -8.82, spxPnL: -20.0, relative: 11.18 },
  { scenario: 'Rates +200bps', portfolioPnL: -3.45, spxPnL: -5.2, relative: 1.75 },
  { scenario: 'USD +10%', portfolioPnL: -1.82, spxPnL: -2.1, relative: 0.28 },
  { scenario: 'Credit Crisis', portfolioPnL: -12.50, spxPnL: -18.5, relative: 6.0 },
  { scenario: 'Stagflation', portfolioPnL: -6.20, spxPnL: -12.0, relative: 5.8 },
  { scenario: 'Risk-Off Rotation', portfolioPnL: -5.15, spxPnL: -8.5, relative: 3.35 },
];

const mockComplianceChecks = [
  { rule: 'Max single position', limit: '10%', current: '8.2%', status: 'Pass' },
  { rule: 'Max sector weight', limit: '40%', current: '38.5%', status: 'Pass' },
  { rule: 'Min positions', limit: '25', current: '42', status: 'Pass' },
  { rule: 'Max leverage', limit: '1.0x', current: '0.95x', status: 'Warning' },
  { rule: 'Max VaR (95%)', limit: '$500K', current: '$385K', status: 'Pass' },
];

const mockFactorExposure = [
  { factor: 'Market', exposure: 1.08, benchmark: 1.0, active: 0.08 },
  { factor: 'Size', exposure: 0.35, benchmark: 0.15, active: 0.20 },
  { factor: 'Value', exposure: -0.22, benchmark: 0.0, active: -0.22 },
  { factor: 'Momentum', exposure: 0.45, benchmark: 0.10, active: 0.35 },
  { factor: 'Quality', exposure: 0.62, benchmark: 0.20, active: 0.42 },
  { factor: 'Low Vol', exposure: -0.18, benchmark: 0.05, active: -0.23 },
];

const mockCorrelationTickers = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL'];
const mockCorrelationMatrix = [
  [1.0, 0.72, 0.68, 0.55, 0.61],
  [0.72, 1.0, 0.78, 0.60, 0.65],
  [0.68, 0.78, 1.0, 0.62, 0.70],
  [0.55, 0.60, 0.62, 1.0, 0.58],
  [0.61, 0.65, 0.70, 0.58, 1.0],
];

const mockDriftData = [
  { asset: 'US Equity', target: 40.0, actual: 42.5, drift: 2.5, status: 'Warning' },
  { asset: 'Intl Equity', target: 20.0, actual: 18.2, drift: -1.8, status: 'OK' },
  { asset: 'Fixed Income', target: 25.0, actual: 24.1, drift: -0.9, status: 'OK' },
  { asset: 'Alternatives', target: 10.0, actual: 11.8, drift: 1.8, status: 'Warning' },
  { asset: 'Cash', target: 5.0, actual: 3.4, drift: -1.6, status: 'OK' },
];

export default function RiskPage() {
  const { portfolioId } = useParams<{ portfolioId: string }>();

  // API hooks
  const { data: apiVaR } = usePortfolioVaR(portfolioId);
  const { data: apiCVaR } = usePortfolioCVaR(portfolioId);
  const { data: apiConcentration } = usePortfolioConcentration(portfolioId);
  const { data: apiStress } = usePortfolioStressHistorical(portfolioId);
  const { data: apiCompliance } = usePortfolioCompliance(portfolioId);
  const { data: apiFactors } = usePortfolioFactorExposure(portfolioId);
  const { data: apiCorrelation } = usePortfolioCorrelation(portfolioId);
  const { data: apiDrift } = usePortfolioDrift(portfolioId);

  // Merge API data with mock fallbacks
  const riskKPIs = (apiVaR && apiCVaR) ? [
    { label: '1D VaR (95%)', value: (apiVaR as any)?.var95_1d ?? '$385K' },
    { label: '1D VaR (99%)', value: (apiVaR as any)?.var99_1d ?? '$620K' },
    { label: '10D VaR (95%)', value: (apiVaR as any)?.var95_10d ?? '$1.22M' },
    { label: 'CVaR (95%)', value: (apiCVaR as any)?.cvar95 ?? '$580K' },
    { label: 'Tracking Error', value: (apiVaR as any)?.trackingError ?? '2.8%' },
    { label: 'Active Share', value: (apiVaR as any)?.activeShare ?? '42.5%' },
  ] : mockRiskKPIs;

  const concentrationRisk = (apiConcentration as any[]) ?? mockConcentrationRisk;
  const stressResults = (apiStress as any[]) ?? mockStressResults;
  const complianceChecks = (apiCompliance as any[]) ?? mockComplianceChecks;
  const factorExposure = (apiFactors as any[]) ?? mockFactorExposure;

  const correlationTickers = (apiCorrelation as any)?.tickers ?? mockCorrelationTickers;
  const correlationMatrix = (apiCorrelation as any)?.matrix ?? mockCorrelationMatrix;

  const driftData = (apiDrift as any)?.allocations ?? mockDriftData;

  // Custom stress test state
  const [customScenarioName, setCustomScenarioName] = useState('');
  const [customEquityShock, setCustomEquityShock] = useState<number>(0);
  const [customRateShock, setCustomRateShock] = useState<number>(0);
  const [customStressResult, setCustomStressResult] = useState<any>(null);
  const [customStressLoading, setCustomStressLoading] = useState(false);
  const [customStressError, setCustomStressError] = useState<string | null>(null);

  const handleRunCustomStress = useCallback(async () => {
    if (!portfolioId) return;
    setCustomStressLoading(true);
    setCustomStressError(null);
    setCustomStressResult(null);
    try {
      const result = await api.request(`/v4/portfolios/${portfolioId}/risk/stress/custom`, {
        method: 'POST',
        body: JSON.stringify({
          scenarioName: customScenarioName,
          equityShockPct: customEquityShock,
          rateShockBps: customRateShock,
        }),
      });
      setCustomStressResult(result);
    } catch (err: any) {
      setCustomStressError(err?.message ?? 'Failed to run custom stress test');
    } finally {
      setCustomStressLoading(false);
    }
  }, [portfolioId, customScenarioName, customEquityShock, customRateShock]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Portfolio Risk</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>VaR analysis, concentration, stress tests, and compliance</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {riskKPIs.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Concentration Analysis</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Dimension', 'Weight', 'VaR Contribution'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Dimension' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {concentrationRisk.map((c: any) => (
                <tr key={c.name} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.weight.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.varContribution > 50 ? 'var(--color-signal-warning)' : 'var(--color-text-primary)' }}>{c.varContribution.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Compliance Checks</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Rule', 'Limit', 'Current', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Rule' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {complianceChecks.map((c: any) => (
                <tr key={c.rule} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.rule}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{c.limit}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.current}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.status === 'Pass' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)', fontWeight: 500 }}>{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Stress Test Results</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Scenario', 'Portfolio P&L', 'S&P 500 P&L', 'Relative'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Scenario' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {stressResults.map((s: any) => (
                <tr key={s.scenario} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.scenario}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)', fontWeight: 600 }}>{s.portfolioPnL.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{s.spxPnL.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)', fontWeight: 500 }}>+{s.relative.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Factor Exposure */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Factor Exposure</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Factor', 'Exposure', 'Benchmark', 'Active'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Factor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {factorExposure.map((f: any) => (
                <tr key={f.factor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.factor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{f.exposure.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{f.benchmark.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.active >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>{f.active >= 0 ? '+' : ''}{f.active.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Drift Monitoring */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Drift Monitoring</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Asset', 'Target %', 'Actual %', 'Drift %', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Asset' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {driftData.map((d: any) => (
                <tr key={d.asset} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.asset}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{d.target.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{d.actual.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: Math.abs(d.drift) >= 2.0 ? 'var(--color-signal-warning)' : 'var(--color-text-primary)' }}>{d.drift >= 0 ? '+' : ''}{d.drift.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status === 'OK' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)', fontWeight: 500 }}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Correlation Matrix */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Correlation Matrix</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}></th>
                  {correlationTickers.map((t: string) => (
                    <th key={t} style={{ ...labelStyle, textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', minWidth: '70px' }}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {correlationTickers.map((rowTicker: string, rowIdx: number) => (
                  <tr key={rowTicker} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{rowTicker}</td>
                    {correlationMatrix[rowIdx]?.map((val: number, colIdx: number) => {
                      const bg = rowIdx === colIdx
                        ? 'var(--color-surface-border)'
                        : val >= 0.7
                          ? 'rgba(255, 80, 80, 0.15)'
                          : val >= 0.5
                            ? 'rgba(255, 165, 0, 0.10)'
                            : 'transparent';
                      return (
                        <td key={colIdx} style={{ ...dataStyle, textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', background: bg }}>{val.toFixed(2)}</td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Custom Stress Test */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Custom Stress Test</h2>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={labelStyle}>Scenario Name</label>
              <input
                type="text"
                value={customScenarioName}
                onChange={(e) => setCustomScenarioName(e.target.value)}
                placeholder="e.g. Custom Drawdown"
                style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: '6px 10px', background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)', minWidth: '180px' }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={labelStyle}>Equity Shock %</label>
              <input
                type="number"
                value={customEquityShock}
                onChange={(e) => setCustomEquityShock(Number(e.target.value))}
                style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', padding: '6px 10px', background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)', width: '100px' }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={labelStyle}>Rate Shock (bps)</label>
              <input
                type="number"
                value={customRateShock}
                onChange={(e) => setCustomRateShock(Number(e.target.value))}
                style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', padding: '6px 10px', background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)', width: '100px' }}
              />
            </div>
            <button
              onClick={handleRunCustomStress}
              disabled={customStressLoading || !customScenarioName}
              style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, padding: '6px 16px', background: 'var(--color-accent)', color: '#fff', border: 'none', borderRadius: '3px', cursor: customStressLoading || !customScenarioName ? 'not-allowed' : 'pointer', opacity: customStressLoading || !customScenarioName ? 0.5 : 1 }}
            >
              {customStressLoading ? 'Running...' : 'Run Custom Stress'}
            </button>
          </div>
          {customStressError && (
            <div style={{ ...labelStyle, color: 'var(--color-signal-negative)', marginTop: '12px' }}>{customStressError}</div>
          )}
          {customStressResult && (
            <div style={{ marginTop: '12px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  {['Metric', 'Value'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {Object.entries(customStressResult).map(([key, val]) => (
                    <tr key={key} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{key}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{typeof val === 'number' ? (val as number).toFixed(2) : String(val)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
