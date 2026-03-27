// ---------------------------------------------------------------------------
// Risk Page — Portfolio VaR, Concentration, Stress Tests
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const riskKPIs = [
  { label: '1D VaR (95%)', value: '$385K' },
  { label: '1D VaR (99%)', value: '$620K' },
  { label: '10D VaR (95%)', value: '$1.22M' },
  { label: 'CVaR (95%)', value: '$580K' },
  { label: 'Tracking Error', value: '2.8%' },
  { label: 'Active Share', value: '42.5%' },
];

const concentrationRisk = [
  { name: 'Top 1 Holding', weight: 8.2, ticker: 'NVDA', varContribution: 18.5 },
  { name: 'Top 5 Holdings', weight: 32.8, ticker: 'Various', varContribution: 52.1 },
  { name: 'Top 10 Holdings', weight: 55.2, ticker: 'Various', varContribution: 72.8 },
  { name: 'Top Sector (Tech)', weight: 38.5, ticker: 'XLK', varContribution: 45.2 },
  { name: 'Top Country (US)', weight: 82.3, ticker: 'US', varContribution: 78.5 },
];

const stressResults = [
  { scenario: 'Equity -20%', portfolioPnL: -8.82, spxPnL: -20.0, relative: 11.18 },
  { scenario: 'Rates +200bps', portfolioPnL: -3.45, spxPnL: -5.2, relative: 1.75 },
  { scenario: 'USD +10%', portfolioPnL: -1.82, spxPnL: -2.1, relative: 0.28 },
  { scenario: 'Credit Crisis', portfolioPnL: -12.50, spxPnL: -18.5, relative: 6.0 },
  { scenario: 'Stagflation', portfolioPnL: -6.20, spxPnL: -12.0, relative: 5.8 },
  { scenario: 'Risk-Off Rotation', portfolioPnL: -5.15, spxPnL: -8.5, relative: 3.35 },
];

const complianceChecks = [
  { rule: 'Max single position', limit: '10%', current: '8.2%', status: 'Pass' },
  { rule: 'Max sector weight', limit: '40%', current: '38.5%', status: 'Pass' },
  { rule: 'Min positions', limit: '25', current: '42', status: 'Pass' },
  { rule: 'Max leverage', limit: '1.0x', current: '0.95x', status: 'Warning' },
  { rule: 'Max VaR (95%)', limit: '$500K', current: '$385K', status: 'Pass' },
];

export default function RiskPage() {
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
              {concentrationRisk.map((c) => (
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
              {complianceChecks.map((c) => (
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
              {stressResults.map((s) => (
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
      </div>
    </div>
  );
}
