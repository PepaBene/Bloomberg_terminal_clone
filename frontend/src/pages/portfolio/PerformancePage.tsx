// ---------------------------------------------------------------------------
// Performance Page — Returns Chart, Calendar Returns, Risk Metrics
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };
function signalColor(v: number): string { return v >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)'; }

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

export default function PerformancePage() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Performance &amp; Attribution</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Portfolio returns, risk-adjusted metrics, and calendar analysis</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {perfKPIs.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: k.value.startsWith('+') ? 'var(--color-signal-positive)' : k.value.startsWith('-') ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      {/* Chart Placeholder */}
      <div style={{ ...panelStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '180px', borderStyle: 'dashed', marginBottom: 'var(--panel-gap)' }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: 'var(--color-text-tertiary)' }}>Cumulative Returns Chart &mdash; Coming Soon</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Calendar Returns */}
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
              {calendarReturns.map((r) => (
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
              {riskMetrics.map((r) => (
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
    </div>
  );
}
