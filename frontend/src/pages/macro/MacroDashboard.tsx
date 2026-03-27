// ---------------------------------------------------------------------------
// Macro Dashboard — Economic Indicators, GDP, Inflation, Employment
// ---------------------------------------------------------------------------

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

// --- Mock Data ---------------------------------------------------------------

const headlineKPIs = [
  { label: 'GDP (QoQ SAAR)', value: '2.4%' },
  { label: 'CPI YoY', value: '3.1%' },
  { label: 'Core PCE YoY', value: '2.8%' },
  { label: 'Unemployment', value: '3.8%' },
  { label: 'Fed Funds Rate', value: '5.25-5.50%' },
  { label: 'ISM Mfg', value: '48.2' },
];

const gdpComponents = [
  { component: 'Personal Consumption', q1: 2.8, q4: 3.3, q3: 3.6 },
  { component: 'Gross Private Investment', q1: 1.2, q4: 0.8, q3: -1.5 },
  { component: 'Net Exports', q1: -0.4, q4: -0.2, q3: 0.6 },
  { component: 'Government Spending', q1: 0.8, q4: 0.5, q3: 0.8 },
  { component: 'GDP Total', q1: 2.4, q4: 3.2, q3: 4.9 },
];

const inflationData = [
  { metric: 'CPI YoY', latest: 3.1, prior: 3.4, trend: 'down' },
  { metric: 'Core CPI YoY', latest: 3.8, prior: 3.9, trend: 'down' },
  { metric: 'PCE YoY', latest: 2.5, prior: 2.6, trend: 'down' },
  { metric: 'Core PCE YoY', latest: 2.8, prior: 2.8, trend: 'flat' },
  { metric: 'PPI YoY', latest: 0.9, prior: 1.0, trend: 'down' },
];

const employmentData = [
  { metric: 'NFP (000s)', latest: '275', prior: '229', surprise: '+46' },
  { metric: 'Unemployment Rate', latest: '3.8%', prior: '3.7%', surprise: '+0.1%' },
  { metric: 'Avg Hourly Earnings YoY', latest: '4.3%', prior: '4.4%', surprise: '-0.1%' },
  { metric: 'Labor Force Part Rate', latest: '62.5%', prior: '62.5%', surprise: '0.0%' },
  { metric: 'JOLTS Openings (M)', latest: '8.86', prior: '8.89', surprise: '-0.03' },
];

// --- Component ---------------------------------------------------------------

export default function MacroDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Macro Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>US economic indicators &mdash; GDP, inflation, employment, and activity</p>
      </div>

      {/* Headline KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {headlineKPIs.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* GDP Components */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>GDP Components (QoQ SAAR)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Component', 'Q1 2026', 'Q4 2025', 'Q3 2025'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Component' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {gdpComponents.map((g) => (
                <tr key={g.component} style={{ height: 'var(--table-row-height)', fontWeight: g.component === 'GDP Total' ? 600 : 400 }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: g.component === 'GDP Total' ? 600 : 400 }}>{g.component}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: g.q1 >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{g.q1 >= 0 ? '+' : ''}{g.q1.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{g.q4 >= 0 ? '+' : ''}{g.q4.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{g.q3 >= 0 ? '+' : ''}{g.q3.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Inflation */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Inflation Metrics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Metric', 'Latest', 'Prior', 'Trend'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {inflationData.map((d) => (
                <tr key={d.metric} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.metric}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{d.latest.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{d.prior.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.trend === 'down' ? 'var(--color-signal-positive)' : 'var(--color-text-secondary)' }}>
                    {d.trend === 'down' ? '\u2193' : d.trend === 'up' ? '\u2191' : '\u2194'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Employment */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Employment Data</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Metric', 'Latest', 'Prior', 'Surprise'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {employmentData.map((e) => (
                <tr key={e.metric} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.metric}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{e.latest}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{e.prior}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: e.surprise.startsWith('+') ? 'var(--color-signal-positive)' : e.surprise.startsWith('-') ? 'var(--color-signal-negative)' : 'var(--color-text-secondary)' }}>{e.surprise}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
