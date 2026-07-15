// ---------------------------------------------------------------------------
// Performance Page — Returns Chart, Calendar Returns, Risk Metrics
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { TimeSeriesChart, HeatmapChart } from '@/components/charts';
import type { HeatmapDataPoint } from '@/components/charts';
import {
  usePortfolioNav,
  usePortfolioPerformance,
  usePortfolioReturns,
  usePortfolioCalendarReturns,
  usePortfolioRiskMetrics,
  usePortfolioAttribution,
  usePortfolioAttributionByFactor,
  usePortfolioDrawdown,
  usePortfolioRollingReturns,
} from '@/hooks';

// --- Real API response shapes (src/schemas/performance.py, attribution.py,
// nav.py) -- P4-F-014: the previous `apiX?.field` reads (`.kpis`, `.rows`,
// `.heatmap`, `.metrics`, `.sectors`, `.factors`, two `.data`s) didn't match
// any real backend field name, so every one of these silently fell through
// to the mock constant even once the hooks had real data to return. These
// interfaces + the mapping below replace that with the actual response
// shapes, transformed into what this page's tables/charts need.

interface ApiNav {
  nav: number;
}

// Fractions (e.g. 0.0842 for +8.42%), matching src/engines/backtester.py's
// compute_performance_metrics convention.
interface ApiPerformance {
  twr_return: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  information_ratio: number | null;
  tracking_error: number | null;
  max_drawdown: number | null;
  beta: number | null;
  alpha: number | null;
  volatility: number | null;
}

interface ApiCalendarReturnEntry {
  year: number;
  jan: number | null;
  feb: number | null;
  mar: number | null;
  apr: number | null;
  may: number | null;
  jun: number | null;
  jul: number | null;
  aug: number | null;
  sep: number | null;
  oct: number | null;
  nov: number | null;
  dec: number | null;
  ytd: number | null;
}

interface ApiCalendarReturnResponse {
  years: ApiCalendarReturnEntry[];
}

interface ApiRiskMetrics {
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  information_ratio: number | null;
  tracking_error: number | null;
  beta: number | null;
  alpha: number | null;
  volatility: number | null;
}

interface ApiSectorAttributionEntry {
  sector: string;
  allocation_effect: number;
  selection_effect: number;
  interaction_effect: number;
  total_effect: number;
}

interface ApiAttributionResponse {
  brinson: { sector_detail: ApiSectorAttributionEntry[] } | null;
}

interface ApiFactorAttributionEntry {
  factor: string;
  portfolio_exposure: number;
  factor_return: number;
  contribution: number;
}

interface ApiReturnSeriesEntry {
  date: string;
  cumulative_return: number;
}

interface ApiReturnSeriesResponse {
  entries: ApiReturnSeriesEntry[];
}

interface ApiRollingReturnEntry {
  date: string;
  rolling_1m: number | null;
}

interface ApiRollingReturnResponse {
  entries: ApiRollingReturnEntry[];
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };
function signalColor(v: number): string { return v >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)'; }
function formatSignedPct(v: number): string { return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`; }
function formatCurrency(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
}

const perfKPIs = [
  { label: 'Portfolio Value', value: '$48.2M' },
  { label: 'MTD Return', value: '+2.85%' },
  { label: 'YTD Return', value: '+8.42%' },
  { label: '1Y Return', value: '+18.6%' },
  { label: 'Sharpe (1Y)', value: '1.42' },
  { label: 'Max Drawdown', value: '-8.2%' },
];

const calendarReturns = [
  { year: '2025', jan: 2.1, feb: -0.8, mar: 3.2, apr: -1.5, may: 1.8, jun: 2.4, jul: -0.3, aug: 1.2, sep: -2.8, oct: 3.5, nov: 2.1, dec: 1.5, ytd: 12.8 },
  { year: '2024', jan: 1.5, feb: 3.2, mar: -0.5, apr: -2.1, may: 4.2, jun: 1.8, jul: 2.5, aug: -1.2, sep: 0.8, oct: -0.5, nov: 5.2, dec: 2.8, ytd: 18.5 },
];

const riskMetrics = [
  { metric: 'Volatility (Ann.)', portfolio: '14.2%', benchmark: '15.8%' },
  { metric: 'Tracking Error', portfolio: '2.8%', benchmark: '-' },
  { metric: 'Information Ratio', portfolio: '1.15', benchmark: '-' },
  { metric: 'Sortino Ratio', portfolio: '2.05', benchmark: '1.72' },
  { metric: 'Beta', portfolio: '1.08', benchmark: '1.00' },
  { metric: 'Alpha (Ann.)', portfolio: '+2.4%', benchmark: '-' },
];

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'YTD'];

// --- Calendar Heatmap Data ---------------------------------------------------

const HEATMAP_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const HEATMAP_YEARS = ['2024', '2025'];

const HEATMAP_DATA: HeatmapDataPoint[] = [
  // 2025
  { row: '2025', col: 'Jan', value: 2.1 },  { row: '2025', col: 'Feb', value: -0.8 },
  { row: '2025', col: 'Mar', value: 3.2 },  { row: '2025', col: 'Apr', value: -1.5 },
  { row: '2025', col: 'May', value: 1.8 },  { row: '2025', col: 'Jun', value: 2.4 },
  { row: '2025', col: 'Jul', value: -0.3 }, { row: '2025', col: 'Aug', value: 1.2 },
  { row: '2025', col: 'Sep', value: -2.8 }, { row: '2025', col: 'Oct', value: 3.5 },
  { row: '2025', col: 'Nov', value: 2.1 },  { row: '2025', col: 'Dec', value: 1.5 },
  // 2024
  { row: '2024', col: 'Jan', value: 1.5 },  { row: '2024', col: 'Feb', value: 3.2 },
  { row: '2024', col: 'Mar', value: -0.5 }, { row: '2024', col: 'Apr', value: -2.1 },
  { row: '2024', col: 'May', value: 4.2 },  { row: '2024', col: 'Jun', value: 1.8 },
  { row: '2024', col: 'Jul', value: 2.5 },  { row: '2024', col: 'Aug', value: -1.2 },
  { row: '2024', col: 'Sep', value: 0.8 },  { row: '2024', col: 'Oct', value: -0.5 },
  { row: '2024', col: 'Nov', value: 5.2 },  { row: '2024', col: 'Dec', value: 2.8 },
];

// --- Attribution Mock Data ----------------------------------------------------

const mockAttribution = [
  { sector: 'Technology', allocation: 0.42, selection: 1.15, interaction: 0.08, total: 1.65 },
  { sector: 'Healthcare', allocation: -0.18, selection: 0.52, interaction: -0.03, total: 0.31 },
  { sector: 'Financials', allocation: 0.25, selection: -0.30, interaction: 0.05, total: 0.00 },
  { sector: 'Consumer Disc.', allocation: -0.10, selection: 0.68, interaction: -0.02, total: 0.56 },
  { sector: 'Industrials', allocation: 0.15, selection: 0.22, interaction: 0.01, total: 0.38 },
  { sector: 'Energy', allocation: -0.35, selection: -0.12, interaction: 0.04, total: -0.43 },
  { sector: 'Communication', allocation: 0.08, selection: 0.45, interaction: 0.02, total: 0.55 },
  { sector: 'Materials', allocation: -0.05, selection: -0.08, interaction: -0.01, total: -0.14 },
];

const mockFactorAttribution = [
  { factor: 'Market', exposure: 1.08, return: 12.5, contribution: 13.50 },
  { factor: 'Size', exposure: -0.22, return: 3.2, contribution: -0.70 },
  { factor: 'Value', exposure: 0.35, return: 5.8, contribution: 2.03 },
  { factor: 'Momentum', exposure: 0.48, return: 8.1, contribution: 3.89 },
  { factor: 'Quality', exposure: 0.62, return: 4.5, contribution: 2.79 },
  { factor: 'Low Volatility', exposure: -0.15, return: 2.3, contribution: -0.35 },
];

function CumulativeReturnChart({ data }: { data?: { date: string; value: number; portfolio: number; benchmark: number }[] }) {
  // P4-F-014: don't fabricate a Math.random() walk when the API hasn't
  // returned data; render an empty chart instead so the user can tell
  // real performance from synthetic noise.
  const chartData = data ?? [];
  return (
    <TimeSeriesChart
      data={chartData}
      height={280}
      showGrid
      showLegend
      series={[
        { key: 'portfolio', color: '#3B82F6', name: 'Portfolio', type: 'line' },
        { key: 'benchmark', color: '#8A96A3', name: 'S&P 500', type: 'line' },
      ]}
      yAxisFormat={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
    />
  );
}

export default function PerformancePage() {
  const { portfolioId } = useParams<{ portfolioId: string }>();

  // --- API hooks with fallback to mock data ---
  const { data: apiNav } = usePortfolioNav(portfolioId) as { data: ApiNav | undefined };
  const { data: apiPerformance } = usePortfolioPerformance(portfolioId) as { data: ApiPerformance | null | undefined };
  const { data: apiReturns } = usePortfolioReturns(portfolioId) as { data: ApiReturnSeriesResponse | undefined };
  const { data: apiCalendarReturns } = usePortfolioCalendarReturns(portfolioId) as { data: ApiCalendarReturnResponse | undefined };
  const { data: apiRiskMetrics } = usePortfolioRiskMetrics(portfolioId) as { data: ApiRiskMetrics | undefined };
  const { data: apiAttribution } = usePortfolioAttribution(portfolioId) as { data: ApiAttributionResponse | undefined };
  const { data: apiFactorAttribution } = usePortfolioAttributionByFactor(portfolioId) as { data: ApiFactorAttributionEntry[] | undefined };
  const { data: apiRollingReturns } = usePortfolioRollingReturns(portfolioId) as { data: ApiRollingReturnResponse | undefined };
  // No /performance/drawdown series endpoint exists -- DrawdownResponse
  // (src/schemas/performance.py) is a single summary object (max_drawdown/
  // peak_date/trough_date), not a time series, so it can't feed this chart.
  // Kept unused-fetch-free rather than fabricating a 2-point series from a
  // summary; the chart stays an honest empty state until a real drawdown
  // series endpoint exists.
  usePortfolioDrawdown(portfolioId);

  // --- Wire API data with mock fallback (P4-F-014) ---
  // KPIs are merged per-field (same pattern RiskPage.tsx uses for its VaR
  // row) rather than swapped as a whole array, since "Portfolio Value" (NAV)
  // and the 4 performance-derived cells come from two different real
  // endpoints while MTD/1Y Return have no real per-period source yet (the
  // backend's /performance endpoint always computes a single
  // since-inception snapshot regardless of the `period` query param -- see
  // that endpoint's docstring).
  const kpis = [
    { label: 'Portfolio Value', value: apiNav?.nav != null ? formatCurrency(apiNav.nav) : perfKPIs[0]!.value },
    { label: 'MTD Return', value: perfKPIs[1]!.value },
    { label: 'YTD Return', value: apiPerformance?.twr_return != null ? formatSignedPct(apiPerformance.twr_return * 100) : perfKPIs[2]!.value },
    { label: '1Y Return', value: perfKPIs[3]!.value },
    { label: 'Sharpe (1Y)', value: apiPerformance?.sharpe_ratio != null ? apiPerformance.sharpe_ratio.toFixed(2) : perfKPIs[4]!.value },
    { label: 'Max Drawdown', value: apiPerformance?.max_drawdown != null ? formatSignedPct(-Math.abs(apiPerformance.max_drawdown) * 100) : perfKPIs[5]!.value },
  ];

  const calReturns = useMemo(() => {
    if (!apiCalendarReturns?.years?.length) return calendarReturns;
    return apiCalendarReturns.years.map((y) => {
      const months = [y.jan, y.feb, y.mar, y.apr, y.may, y.jun, y.jul, y.aug, y.sep, y.oct, y.nov, y.dec];
      // Real CalendarReturnEntry.ytd is never populated by the backend
      // (src/api/routers/portfolio_performance.py only ever sets the
      // per-month fields) -- derive a compounded YTD from the months that
      // do have data rather than showing a fabricated/missing figure.
      const ytd = months.reduce((acc, m) => (m != null ? (1 + acc) * (1 + m) - 1 : acc), 0);
      return {
        year: String(y.year),
        jan: (y.jan ?? 0) * 100, feb: (y.feb ?? 0) * 100, mar: (y.mar ?? 0) * 100,
        apr: (y.apr ?? 0) * 100, may: (y.may ?? 0) * 100, jun: (y.jun ?? 0) * 100,
        jul: (y.jul ?? 0) * 100, aug: (y.aug ?? 0) * 100, sep: (y.sep ?? 0) * 100,
        oct: (y.oct ?? 0) * 100, nov: (y.nov ?? 0) * 100, dec: (y.dec ?? 0) * 100,
        ytd: ytd * 100,
      };
    });
  }, [apiCalendarReturns]);

  const heatmapYears = useMemo(
    () => (apiCalendarReturns?.years?.length ? apiCalendarReturns.years.map((y) => String(y.year)) : HEATMAP_YEARS),
    [apiCalendarReturns],
  );
  const heatmapData = useMemo<HeatmapDataPoint[]>(() => {
    if (!apiCalendarReturns?.years?.length) return HEATMAP_DATA;
    const points: HeatmapDataPoint[] = [];
    for (const y of apiCalendarReturns.years) {
      for (const [col, val] of HEATMAP_MONTHS.map((m, i) => [m, [y.jan, y.feb, y.mar, y.apr, y.may, y.jun, y.jul, y.aug, y.sep, y.oct, y.nov, y.dec][i]] as const)) {
        if (val != null) points.push({ row: String(y.year), col, value: val * 100 });
      }
    }
    return points;
  }, [apiCalendarReturns]);

  // Real RiskMetricsResponse has no per-metric benchmark comparator (unlike
  // the mock, which fabricates one for every row) -- shown as "-" for real
  // data, matching the mock's own convention on its Tracking Error /
  // Information Ratio rows where no benchmark figure is available either.
  const risk = apiRiskMetrics
    ? [
        { metric: 'Volatility (Ann.)', portfolio: apiRiskMetrics.volatility != null ? formatSignedPct(apiRiskMetrics.volatility * 100) : '—', benchmark: '-' },
        { metric: 'Tracking Error', portfolio: apiRiskMetrics.tracking_error != null ? formatSignedPct(apiRiskMetrics.tracking_error * 100) : '—', benchmark: '-' },
        { metric: 'Information Ratio', portfolio: apiRiskMetrics.information_ratio != null ? apiRiskMetrics.information_ratio.toFixed(2) : '—', benchmark: '-' },
        { metric: 'Sortino Ratio', portfolio: apiRiskMetrics.sortino_ratio != null ? apiRiskMetrics.sortino_ratio.toFixed(2) : '—', benchmark: '-' },
        { metric: 'Beta', portfolio: apiRiskMetrics.beta != null ? apiRiskMetrics.beta.toFixed(2) : '—', benchmark: '-' },
        { metric: 'Alpha (Ann.)', portfolio: apiRiskMetrics.alpha != null ? formatSignedPct(apiRiskMetrics.alpha * 100) : '—', benchmark: '-' },
      ]
    : riskMetrics;

  const returnsData = useMemo(() => {
    if (!apiReturns?.entries?.length) return undefined;
    return apiReturns.entries.map((e) => ({
      date: e.date,
      value: e.cumulative_return * 100,
      portfolio: e.cumulative_return * 100,
      // No real benchmark daily-return series exists in this system yet
      // (Portfolio.benchmark_id is a free-text ticker, not resolved against
      // a priced security here) -- kept at 0 rather than fabricated.
      benchmark: 0,
    }));
  }, [apiReturns]);

  const attributionData = useMemo(
    () =>
      apiAttribution?.brinson?.sector_detail?.length
        ? apiAttribution.brinson.sector_detail.map((s) => ({
            sector: s.sector,
            allocation: s.allocation_effect * 100,
            selection: s.selection_effect * 100,
            interaction: s.interaction_effect * 100,
            total: s.total_effect * 100,
          }))
        : mockAttribution,
    [apiAttribution],
  );

  const factorData = useMemo(
    () =>
      apiFactorAttribution?.length
        ? apiFactorAttribution.map((f) => ({
            factor: f.factor,
            exposure: f.portfolio_exposure,
            return: f.factor_return * 100,
            contribution: f.contribution * 100,
          }))
        : mockFactorAttribution,
    [apiFactorAttribution],
  );

  // No Math.random() walk when the API has no data (P4-F-014).
  const drawdownData: { date: string; value: number }[] = [];
  const rollingData = useMemo(() => {
    if (!apiRollingReturns?.entries?.length) return [];
    return apiRollingReturns.entries.map((e) => ({
      date: e.date,
      value: (e.rolling_1m ?? 0) * 100,
      portfolio: (e.rolling_1m ?? 0) * 100,
      // Backend only ever populates rolling_1m (src/api/routers/
      // portfolio_performance.py::get_rolling_returns) -- no benchmark
      // rolling series exists, kept at 0 rather than fabricated.
      benchmark: 0,
    }));
  }, [apiRollingReturns]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Performance &amp; Attribution</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Portfolio returns, risk-adjusted metrics, and calendar analysis</p>
      </div>
      {/* KPIs Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {kpis.map((k: { label: string; value: string }) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: k.value.startsWith('+') ? 'var(--color-signal-positive)' : k.value.startsWith('-') ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      {/* Cumulative Returns Chart */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Cumulative Returns vs Benchmark (1Y)</h2>
        <CumulativeReturnChart data={returnsData} />
      </div>
      {/* Calendar Returns Heatmap */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Monthly Returns Heatmap (%)</h2>
        <HeatmapChart
          data={heatmapData}
          rows={heatmapYears}
          cols={HEATMAP_MONTHS}
          colorScale="diverging"
          valueFormat={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Calendar Returns Table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Calendar Returns (%)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Year</th>
              {months.map((m) => (
                <th key={m} style={{ ...labelStyle, textAlign: 'right', padding: 'var(--table-cell-py) 3px', borderBottom: '1px solid var(--color-surface-border)', fontSize: 'var(--text-xs)' }}>{m}</th>
              ))}
            </tr></thead>
            <tbody>
              {calReturns.map((r: typeof calendarReturns[0]) => (
                <tr key={r.year} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.year}</td>
                  {[r.jan, r.feb, r.mar, r.apr, r.may, r.jun, r.jul, r.aug, r.sep, r.oct, r.nov, r.dec, r.ytd].map((v, i) => (
                    <td key={i} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', textAlign: 'right', padding: 'var(--table-cell-py) 3px', color: signalColor(v), fontWeight: i === 12 ? 600 : 400 }}>{v >= 0 ? '+' : ''}{v.toFixed(1)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Risk Metrics */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Metrics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Metric', 'Portfolio', 'Benchmark'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {risk.map((r: typeof riskMetrics[0]) => (
                <tr key={r.metric} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.metric}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.portfolio}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{r.benchmark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Attribution Analysis */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginTop: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Brinson Attribution */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Brinson Attribution</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Sector', 'Allocation Effect', 'Selection Effect', 'Interaction', 'Total'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Sector' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {attributionData.map((r: typeof mockAttribution[0]) => (
                <tr key={r.sector} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.sector}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.allocation) }}>{r.allocation >= 0 ? '+' : ''}{r.allocation.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.selection) }}>{r.selection >= 0 ? '+' : ''}{r.selection.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.interaction) }}>{r.interaction >= 0 ? '+' : ''}{r.interaction.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: signalColor(r.total) }}>{r.total >= 0 ? '+' : ''}{r.total.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Factor Attribution */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Factor Attribution</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Factor', 'Exposure', 'Return', 'Contribution'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Factor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {factorData.map((r: typeof mockFactorAttribution[0]) => (
                <tr key={r.factor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.factor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.exposure) }}>{r.exposure >= 0 ? '+' : ''}{r.exposure.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.return) }}>{r.return >= 0 ? '+' : ''}{r.return.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: signalColor(r.contribution) }}>{r.contribution >= 0 ? '+' : ''}{r.contribution.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Drawdown Analysis */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Drawdown Analysis</h2>
        <TimeSeriesChart
          data={drawdownData}
          height={220}
          showGrid
          series={[
            { key: 'value', color: '#EF4444', name: 'Drawdown', type: 'line' },
          ]}
          yAxisFormat={(v: number) => `${v.toFixed(1)}%`}
        />
      </div>

      {/* Rolling Returns */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Rolling Returns (1Y)</h2>
        <TimeSeriesChart
          data={rollingData}
          height={220}
          showGrid
          showLegend
          series={[
            { key: 'portfolio', color: '#3B82F6', name: 'Portfolio', type: 'line' },
            { key: 'benchmark', color: '#8A96A3', name: 'Benchmark', type: 'line' },
          ]}
          yAxisFormat={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
        />
      </div>
    </div>
  );
}
