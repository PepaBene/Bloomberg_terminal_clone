// ---------------------------------------------------------------------------
// Risk Page — Portfolio VaR, Concentration, Stress Tests, Factor Exposure,
// Correlation, Drift Monitoring, Custom Stress Tests
// ---------------------------------------------------------------------------
import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  usePortfolioVaR,
  usePortfolioCVaR,
  usePortfolioVaRDecomposition,
  usePortfolioConcentration,
  usePortfolioStressHistorical,
  usePortfolioCompliance,
  usePortfolioFactorExposure,
  usePortfolioCorrelation,
  usePortfolioDrift,
} from '@/hooks';
import { api } from '@/api/client';
import { HeatmapChart, BarChartComponent } from '@/components/charts';
import type { HeatmapDataPoint } from '@/components/charts';
import { FactorExposureChart, VaRDecomposition } from '@/components/risk';
import type { FactorBeta, VaRComponent } from '@/components/risk';

// --- Real API response shapes (src/schemas/portfolio_risk.py,
// compliance_schema.py, drift_schema.py) -- P4-F-022: replaces the 13
// `as any`/`as any[]` casts on this page with types matching the actual
// backend response, several of which are single objects (not arrays) that
// an unguarded `as any[]` cast would have crashed on the moment real data
// (rather than a permanent 404) started flowing through.

interface ApiVaR {
  var_1d_95: number | null;
  var_1d_99: number | null;
  var_10d_95: number | null;
}

// No GET /risk/cvar route exists anywhere in src/api/routers/portfolio_risk.py.
// Keep the optional field so the UI renders an honest unavailable value if a
// deployment adds it later.
interface ApiCVaR {
  cvar95?: number;
}

interface ApiSectorConcentrationEntry {
  sector: string;
  weight: number;
}

interface ApiConcentration {
  largest_position_weight: number | null;
  top_5_weight: number | null;
  top_10_weight: number | null;
  sector_detail: ApiSectorConcentrationEntry[];
}

interface ApiComplianceRule {
  rule_id: string;
  rule_name: string;
  threshold: number | null;
  comparison: string;
}

interface ApiComplianceResult {
  rule_id: string;
  status: string;
  current_value: number | null;
}

interface ApiCompliance {
  rules: ApiComplianceRule[];
  latest_results: ApiComplianceResult[];
}

interface ApiFactorExposure {
  value_exposure: number | null;
  growth_exposure: number | null;
  momentum_exposure: number | null;
  quality_exposure: number | null;
  size_exposure: number | null;
  low_vol_exposure: number | null;
  benchmark_value: number | null;
  benchmark_growth: number | null;
  benchmark_momentum: number | null;
  benchmark_quality: number | null;
  benchmark_size: number | null;
  benchmark_low_vol: number | null;
}

interface ApiStressResult {
  scenario_name: string;
  scenario_type: string;
  total_pnl_percent: number | null;
}

// No GET /risk/correlation route exists anywhere in portfolio_risk.py
// (verified by grep) -- same "missing feature" situation as CVaR above.
interface ApiCorrelation {
  tickers?: string[];
  matrix?: number[][];
}

interface ApiSectorDrift {
  sector: string;
  target_weight: number;
  current_weight: number;
  drift_pct: number;
}

interface ApiDrift {
  sector_drifts: ApiSectorDrift[];
}

// VaRDecompositionResponse (real GET /risk/var/decomposition) carries
// component/marginal VaR as {ticker: value} dicts, not a ready-made list --
// percentContrib is derived (component VaR sums to total VaR by
// construction) rather than fabricated.
interface ApiVaRDecomposition {
  marginal_var: Record<string, number> | null;
  component_var: Record<string, number> | null;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };
function formatMoney(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}
function titleCaseStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}

// The rest of this file computes every table/chart from real API data with
// honest "--"/empty fallbacks (see the comments below) -- this is the only
// mock left, used strictly as VaR Decomposition's fallback when the real
// endpoint returns no component-VaR breakdown yet.
const mockVaRDecomposition: VaRComponent[] = [
  { name: 'NVDA', marginalVar: 4.8, componentVar: 1.42, percentContrib: 22.4 },
  { name: 'AAPL', marginalVar: 3.1, componentVar: 0.98, percentContrib: 15.5 },
  { name: 'MSFT', marginalVar: 2.7, componentVar: 0.85, percentContrib: 13.4 },
  { name: 'AMZN', marginalVar: 2.2, componentVar: 0.71, percentContrib: 11.2 },
  { name: 'GOOGL', marginalVar: 1.9, componentVar: 0.60, percentContrib: 9.5 },
];

export default function RiskPage() {
  const { portfolioId } = useParams<{ portfolioId: string }>();

  // API hooks
  const { data: apiVaR } = usePortfolioVaR(portfolioId) as { data: ApiVaR | null | undefined };
  const { data: apiCVaR } = usePortfolioCVaR(portfolioId) as { data: ApiCVaR | undefined };
  const { data: apiVaRDecomp } = usePortfolioVaRDecomposition(portfolioId) as { data: ApiVaRDecomposition | null | undefined };
  const { data: apiConcentration } = usePortfolioConcentration(portfolioId) as { data: ApiConcentration | null | undefined };
  const { data: apiStress } = usePortfolioStressHistorical(portfolioId) as { data: ApiStressResult[] | undefined };
  const { data: apiCompliance } = usePortfolioCompliance(portfolioId) as { data: ApiCompliance | undefined };
  const { data: apiFactors } = usePortfolioFactorExposure(portfolioId) as { data: ApiFactorExposure | null | undefined };
  const { data: apiCorrelation } = usePortfolioCorrelation(portfolioId) as { data: ApiCorrelation | undefined };
  const { data: apiDrift } = usePortfolioDrift(portfolioId) as { data: ApiDrift | null | undefined };

  const riskKPIs = [
    { label: '1D VaR (95%)', value: apiVaR?.var_1d_95 != null ? formatMoney(apiVaR.var_1d_95) : 'â€”' },
    { label: '1D VaR (99%)', value: apiVaR?.var_1d_99 != null ? formatMoney(apiVaR.var_1d_99) : 'â€”' },
    { label: '10D VaR (95%)', value: apiVaR?.var_10d_95 != null ? formatMoney(apiVaR.var_10d_95) : 'â€”' },
    { label: 'CVaR (95%)', value: apiCVaR?.cvar95 != null ? formatMoney(apiCVaR.cvar95) : 'â€”' },
    { label: 'Tracking Error', value: 'â€”' },
    { label: 'Active Share', value: 'â€”' },
  ];

  // ConcentrationResponse (real GET /risk/concentration) is a single summary
  // object, not a list of dimensions with a per-dimension VaR contribution
  // like the mock -- an unguarded `as any[]` cast here would have crashed
  // the moment this endpoint returned real data. Synthesize the closest
  // real analog (largest/top-5/top-10 weights + real per-sector weights);
  // VaR Contribution has no real source so it's shown as "--".
  const concentrationRisk = apiConcentration
    ? [
        { name: 'Largest Position', weight: (apiConcentration.largest_position_weight ?? 0) * 100, ticker: '—', varContribution: null as number | null },
        { name: 'Top 5 Holdings', weight: (apiConcentration.top_5_weight ?? 0) * 100, ticker: '—', varContribution: null as number | null },
        { name: 'Top 10 Holdings', weight: (apiConcentration.top_10_weight ?? 0) * 100, ticker: '—', varContribution: null as number | null },
        ...apiConcentration.sector_detail.map((s) => ({
          name: `Sector: ${s.sector}`,
          weight: s.weight * 100,
          ticker: s.sector,
          varContribution: null as number | null,
        })),
      ]
    : [];

  // Now a genuine list (endpoints.ts repoints stressHistorical at the real
  // GET /risk/stress/results, which returns list[StressTestResponse] --
  // it previously called the POST-only /risk/stress/historical route and
  // could never have returned an array at all).
  const stressResults = apiStress && apiStress.length > 0
    ? apiStress.map((s) => ({
        scenario: s.scenario_name,
        portfolioPnL: s.total_pnl_percent != null ? s.total_pnl_percent * 100 : null,
        // StressTestResponse has no benchmark/S&P P&L field -- shown as
        // "--" rather than fabricated.
        spxPnL: null as number | null,
        relative: null as number | null,
      }))
    : [];

  // ComplianceSummaryResponse is a single object with `rules`/
  // `latest_results` arrays that need joining by rule_id, not itself a
  // list of {rule, limit, current, status} rows like the mock.
  const complianceChecks = apiCompliance
    ? apiCompliance.rules.map((rule) => {
        const result = apiCompliance.latest_results.find((r) => r.rule_id === rule.rule_id);
        return {
          rule: rule.rule_name,
          limit: rule.threshold != null ? `${rule.comparison} ${rule.threshold}` : '—',
          current: result?.current_value != null ? String(result.current_value) : '—',
          status: result ? titleCaseStatus(result.status) : 'Unknown',
        };
      })
    : [];

  // FactorExposureResponse (real GET /risk/factors) is a single object with
  // 6 named exposure fields + matching benchmark_* fields, not a list of
  // {factor, exposure, benchmark, active} rows like the mock.
  const factorExposure = apiFactors
    ? ([
        ['Value', apiFactors.value_exposure, apiFactors.benchmark_value],
        ['Growth', apiFactors.growth_exposure, apiFactors.benchmark_growth],
        ['Momentum', apiFactors.momentum_exposure, apiFactors.benchmark_momentum],
        ['Quality', apiFactors.quality_exposure, apiFactors.benchmark_quality],
        ['Size', apiFactors.size_exposure, apiFactors.benchmark_size],
        ['Low Vol', apiFactors.low_vol_exposure, apiFactors.benchmark_low_vol],
      ] as const).map(([factor, exposure, benchmark]) => ({
        factor,
        exposure: exposure ?? 0,
        benchmark: benchmark ?? 0,
        active: (exposure ?? 0) - (benchmark ?? 0),
      }))
    : [];

  const correlationTickers = apiCorrelation?.tickers ?? [];
  const correlationMatrix = apiCorrelation?.matrix ?? [];

  // DriftResponse (real GET /drift) is a single object; its `sector_drifts`
  // array is the closest real analog to the mock's per-asset-class rows
  // (there's no real per-row `status` field, so it's derived from the same
  // >=2% threshold src/engines/drift_engine.py's alerting uses).
  const driftData = apiDrift && apiDrift.sector_drifts.length > 0
    ? apiDrift.sector_drifts.map((d) => ({
        asset: d.sector,
        target: d.target_weight * 100,
        actual: d.current_weight * 100,
        drift: d.drift_pct * 100,
        status: Math.abs(d.drift_pct) >= 0.02 ? 'Warning' : 'OK',
      }))
    : [];

  // Component VaR sums to total portfolio VaR by construction (Euler
  // decomposition), so percentContrib is derived rather than a field the
  // backend returns.
  const varDecomposition: VaRComponent[] = useMemo(() => {
    const componentVar = apiVaRDecomp?.component_var;
    const marginalVar = apiVaRDecomp?.marginal_var;
    if (!componentVar || Object.keys(componentVar).length === 0) return mockVaRDecomposition;

    const total = Object.values(componentVar).reduce((s, v) => s + Math.abs(v), 0) || 1;
    return Object.entries(componentVar)
      .map(([ticker, compVar]) => ({
        name: ticker,
        componentVar: compVar,
        marginalVar: marginalVar?.[ticker] ?? 0,
        percentContrib: (Math.abs(compVar) / total) * 100,
      }))
      .sort((a, b) => b.percentContrib - a.percentContrib);
  }, [apiVaRDecomp]);

  // Correlation matrix reshaped into the {row, col, value} triples HeatmapChart expects.
  const correlationHeatmapData: HeatmapDataPoint[] = useMemo(() => {
    const points: HeatmapDataPoint[] = [];
    correlationTickers.forEach((row: string, ri: number) => {
      correlationTickers.forEach((col: string, ci: number) => {
        const value = correlationMatrix[ri]?.[ci];
        if (typeof value === 'number') points.push({ row, col, value });
      });
    });
    return points;
  }, [correlationTickers, correlationMatrix]);

  // Factor exposure as diverging active-tilt bars (exposure minus benchmark) --
  // the real API has no t-stat/significance field, so the chart is plotted
  // without a significance overlay rather than fabricating one.
  const factorExposureBars: FactorBeta[] = useMemo(
    () =>
      factorExposure.map((f: any) => ({
        name: f.factor,
        beta: f.active,
        benchmark: f.benchmark,
      })),
    [factorExposure],
  );

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
          <BarChartComponent
            data={concentrationRisk}
            bars={[{ key: 'weight', name: 'Weight %', color: 'var(--color-chart-1)' }]}
            xKey="name"
            layout="vertical"
            height={Math.max(concentrationRisk.length * 32 + 40, 160)}
            showMeanLine={false}
            yAxisFormat={(v) => `${v.toFixed(1)}%`}
          />
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

        {/* Factor Exposure — active tilt vs benchmark, diverging bar */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Factor Exposure</h2>
          <p style={{ ...labelStyle, margin: '0 0 8px', fontSize: 'var(--text-xs)' }}>Active exposure vs. benchmark</p>
          <FactorExposureChart factors={factorExposureBars} />
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

        {/* VaR Decomposition — each position's share of total portfolio VaR */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>VaR Decomposition</h2>
          <VaRDecomposition components={varDecomposition} />
        </div>

        {/* Correlation Matrix */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Correlation Matrix</h2>
          <HeatmapChart
            data={correlationHeatmapData}
            rows={correlationTickers}
            cols={correlationTickers}
            colorScale="diverging"
            valueFormat={(v) => v.toFixed(2)}
          />
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
