// ---------------------------------------------------------------------------
// Yield Curve Deep Dive — Interactive Curve, Historical Shifts, Spread Analysis
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { YieldCurveChart, TimeSeriesChart } from '@/components/charts';
import type { YieldCurvePoint } from '@/components/charts';
import { EmptyState } from '@/components/feedback';
import {
  useYieldCurve,
  useYieldCurveHistory,
  useYieldCurveForward,
  useRealYieldCurve,
  useBreakevenCurve,
  useSwapCurve,
  useYieldCurveSpreads,
} from '@/hooks';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

function chgColor(v: number): string {
  return v >= 0 ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)';
}

// --- Mock Data ---------------------------------------------------------------

const curveComparison = [
  { tenor: '3M', today: 5.28, w1Ago: 5.30, m1Ago: 5.32, m3Ago: 5.35, y1Ago: 5.40 },
  { tenor: '6M', today: 5.12, w1Ago: 5.15, m1Ago: 5.20, m3Ago: 5.28, y1Ago: 5.38 },
  { tenor: '1Y', today: 4.85, w1Ago: 4.90, m1Ago: 4.98, m3Ago: 5.10, y1Ago: 5.25 },
  { tenor: '2Y', today: 4.52, w1Ago: 4.56, m1Ago: 4.68, m3Ago: 4.85, y1Ago: 5.05 },
  { tenor: '5Y', today: 4.18, w1Ago: 4.21, m1Ago: 4.30, m3Ago: 4.45, y1Ago: 4.65 },
  { tenor: '10Y', today: 4.28, w1Ago: 4.31, m1Ago: 4.38, m3Ago: 4.50, y1Ago: 4.55 },
  { tenor: '30Y', today: 4.52, w1Ago: 4.54, m1Ago: 4.58, m3Ago: 4.65, y1Ago: 4.60 },
];

const keySpreads = [
  { spread: '2s10s', value: -24, chg1w: 1, chg1m: 6, chg3m: 11, chg1y: 26 },
  { spread: '2s30s', value: 0, chg1w: 2, chg1m: 10, chg3m: 20, chg1y: 45 },
  { spread: '5s30s', value: 34, chg1w: 1, chg1m: 4, chg3m: 6, chg1y: 5 },
  { spread: '3m10y', value: -100, chg1w: 2, chg1m: 6, chg3m: 15, chg1y: 15 },
];

const realYields = [
  { tenor: '5Y TIPS', nominal: 4.18, breakeven: 2.28, realYield: 1.90 },
  { tenor: '10Y TIPS', nominal: 4.28, breakeven: 2.32, realYield: 1.96 },
  { tenor: '30Y TIPS', nominal: 4.52, breakeven: 2.35, realYield: 2.17 },
];

// --- Yield Curve Data (current + 3 historical) ------------------------------

const TENORS = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y'];

const CURVE_TODAY: YieldCurvePoint[] = TENORS.map((t, i) => ({
  tenor: t,
  rate: [5.28, 5.12, 4.85, 4.52, 4.18, 4.28, 4.52][i]!,
}));

const CURVE_1M: YieldCurvePoint[] = TENORS.map((t, i) => ({
  tenor: t,
  rate: [5.32, 5.20, 4.98, 4.68, 4.30, 4.38, 4.58][i]!,
}));

// Additional historical curves available via curveComparison table below

// --- 2s10s Spread History — real GET /v1/analytics/yield-curve/spreads/history

interface CurveSpreadHistoryDTO {
  spread_type: string;
  points: { curve_date: string; spread_value: number | null }[];
}

function SpreadHistoryChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['yieldCurve', 'spreadHistory', '2s10s'],
    queryFn: () => api.get<CurveSpreadHistoryDTO>('/v1/analytics/yield-curve/spreads/history', { spread_type: '2s10s' }),
    retry: 0,
  });
  const series = (data?.points ?? [])
    .filter((p) => p.spread_value != null)
    .map((p) => ({ date: p.curve_date, value: Math.round(p.spread_value as number) }))
    .sort((a, b) => a.date.localeCompare(b.date));

  if (isLoading) return <EmptyState icon="⏳" title="Loading spread history…" />;
  if (series.length === 0) {
    return <EmptyState icon="📉" title="No spread history" description="Yield-curve snapshots are required to compute the 2s10s spread series." />;
  }
  return (
    <TimeSeriesChart
      data={series}
      height={220}
      showGrid
      series={[{ key: 'value', color: '#E05252', name: '2s10s Spread (bps)', type: 'area' }]}
      yAxisFormat={(v: number) => `${v}bps`}
      benchmarkLine={{ value: 0, label: 'Zero', color: '#5B7FA6' }}
    />
  );
}

// --- Component ---------------------------------------------------------------

// --- Mock Forward Rates (fallback) -------------------------------------------

const mockForwardRates = [
  { horizon: '1Y1Y', rate: 4.15 },
  { horizon: '1Y2Y', rate: 4.08 },
  { horizon: '2Y1Y', rate: 3.95 },
  { horizon: '1Y5Y', rate: 4.22 },
  { horizon: '5Y5Y', rate: 4.48 },
];

// --- Mock Swap Rates (fallback) ----------------------------------------------

const mockSwapRates = [
  { tenor: '2Y', rate: 4.48 },
  { tenor: '5Y', rate: 4.12 },
  { tenor: '10Y', rate: 4.25 },
  { tenor: '30Y', rate: 4.50 },
];

export default function YieldCurveDeepDive() {
  const { data: apiCurve } = useYieldCurve();
  const { data: apiHistory } = useYieldCurveHistory();
  const { data: apiForward } = useYieldCurveForward();
  const { data: apiReal } = useRealYieldCurve();
  useBreakevenCurve();
  const { data: apiSwap } = useSwapCurve();
  const { data: apiSpreads } = useYieldCurveSpreads();

  const curvePoints = (apiCurve as any)?.points ?? CURVE_TODAY;
  const curveComparisonData = (apiHistory as any)?.comparison ?? curveComparison;
  const keySpreadsData = (apiSpreads as any[]) ?? keySpreads;
  const realYieldsData = (apiReal as any[]) ?? realYields;
  const forwardRatesData = (apiForward as any[]) ?? mockForwardRates;
  const swapRatesData = (apiSwap as any[]) ?? mockSwapRates;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Yield Curve Deep Dive
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>UST yield curve, historical comparison, spread analysis, and real yields</p>
      </div>

      {/* Yield Curve Chart (Current + 3 Historical) */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Yield Curve (Current vs Historical)</h2>
        <YieldCurveChart
          current={curvePoints}
          prior={CURVE_1M}
          priorLabel="1 Month Ago"
          height={300}
        />
      </div>

      {/* 2s10s Spread History */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>2s10s Spread History (1Y)</h2>
        <SpreadHistoryChart />
      </div>

      {/* UST 10Y OAS — no index-level OAS series endpoint exists; honest empty
          state rather than a fabricated random walk (DATA_WIRING_AUDIT §8.3). */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Spread Analysis (UST 10Y OAS)</h2>
        <EmptyState
          icon="📊"
          title="OAS series unavailable"
          description="No index-level UST 10Y OAS time series is wired to this deployment."
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Curve Comparison Table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Curve Comparison (%)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Tenor', 'Today', '1W Ago', '1M Ago', '3M Ago', '1Y Ago'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {curveComparisonData.map((c: any) => (
                <tr key={c.tenor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.today.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{c.w1Ago.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{c.m1Ago.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{c.m3Ago.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{c.y1Ago.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Key Spreads */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Key Spreads (bps)</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Spread', 'Current', '1W', '1M', '3M', '1Y'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Spread' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {keySpreadsData.map((s: any) => (
                  <tr key={s.spread} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.spread}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{s.value}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1w) }}>{s.chg1w > 0 ? '+' : ''}{s.chg1w}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1m) }}>{s.chg1m > 0 ? '+' : ''}{s.chg1m}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg3m) }}>{s.chg3m > 0 ? '+' : ''}{s.chg3m}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1y) }}>{s.chg1y > 0 ? '+' : ''}{s.chg1y}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Real Yields */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>TIPS / Real Yields</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Tenor', 'Nominal', 'Breakeven', 'Real Yield'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {realYieldsData.map((r: any) => (
                  <tr key={r.tenor} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.tenor}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.nominal.toFixed(2)}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.breakeven.toFixed(2)}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.realYield.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Forward Rates */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Forward Rates (%)</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Horizon', 'Implied Rate'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Horizon' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {forwardRatesData.map((f: any) => (
              <tr key={f.horizon} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.horizon}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{Number(f.rate).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Swap Curve */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Swap Curve (%)</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Tenor', 'Swap Rate'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {swapRatesData.map((s: any) => (
              <tr key={s.tenor} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.tenor}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{Number(s.rate).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
