// ---------------------------------------------------------------------------
// Yield Curve Deep Dive — Interactive Curve, Historical Shifts, Spread Analysis
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { YieldCurveChart, TimeSeriesChart } from '@/components/charts';
import type { YieldCurvePoint } from '@/components/charts';
import { SpreadHistoryChart as FISpreadHistoryChart } from '@/components/fi';
import type { SpreadDataPoint } from '@/components/fi';

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

// --- 2s10s Spread History (1 year) -------------------------------------------

function generateSpreadHistory(): { date: string; value: number }[] {
  const data: { date: string; value: number }[] = [];
  let spread = -50;
  const start = new Date('2025-03-27');
  for (let i = 0; i < 252; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const day = d.getDay();
    if (day === 0 || day === 6) continue;
    spread += (Math.random() - 0.48) * 4;
    spread = Math.max(-120, Math.min(20, spread));
    data.push({ date: d.toISOString().slice(0, 10), value: Math.round(spread) });
  }
  return data;
}

function SpreadHistoryChart() {
  const data = useMemo(() => generateSpreadHistory(), []);
  return (
    <TimeSeriesChart
      data={data}
      height={220}
      showGrid
      series={[{ key: 'value', color: '#E05252', name: '2s10s Spread (bps)', type: 'area' }]}
      yAxisFormat={(v: number) => `${v}bps`}
      benchmarkLine={{ value: 0, label: 'Zero', color: '#5B7FA6' }}
    />
  );
}

// --- Component ---------------------------------------------------------------

export default function YieldCurveDeepDive() {
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
          current={CURVE_TODAY}
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

      {/* Spread Analysis via FI SpreadHistoryChart Component */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Spread Analysis (UST 10Y OAS, 12M)</h2>
        <FISpreadHistoryChart
          data={(() => {
            const pts: SpreadDataPoint[] = [];
            let oas = 42;
            const start = new Date('2025-03-28');
            for (let i = 0; i < 252; i++) {
              const d = new Date(start);
              d.setDate(d.getDate() + i);
              const day = d.getDay();
              if (day === 0 || day === 6) continue;
              oas += (Math.random() - 0.48) * 2.5;
              oas = Math.max(20, Math.min(70, oas));
              pts.push({ date: d.toISOString().slice(0, 10), oas: Math.round(oas * 10) / 10 });
            }
            return pts;
          })()}
          benchmarkSpread={42}
          height={220}
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
              {curveComparison.map((c) => (
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
                {keySpreads.map((s) => (
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
                {realYields.map((r) => (
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
    </div>
  );
}
