// ---------------------------------------------------------------------------
// Thesis Builder — Investment Thesis with Key Drivers, Risks, Catalysts
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const thesis = { ticker: 'NVDA', name: 'NVIDIA Corp', direction: 'Long', conviction: 'High', targetPrice: 1050, currentPrice: 878.36, timeframe: '12 months' };

const keyDrivers = [
  { driver: 'AI/ML compute demand accelerating', weight: 35, status: 'Tracking Above' },
  { driver: 'Data center revenue growth >100% YoY', weight: 25, status: 'On Track' },
  { driver: 'Gross margin expansion from software mix', weight: 20, status: 'On Track' },
  { driver: 'New product cycle (Blackwell/Rubin)', weight: 15, status: 'Catalyst Ahead' },
  { driver: 'Sovereign AI demand emerging', weight: 5, status: 'Early Stage' },
];

const risks = [
  { risk: 'Customer concentration (MSFT, AMZN, GOOGL)', probability: 'Medium', impact: 'High', mitigation: 'Diversifying into enterprise/sovereign' },
  { risk: 'China export restrictions tightening', probability: 'High', impact: 'Medium', mitigation: 'Developing compliant SKUs' },
  { risk: 'Custom ASIC competition from hyperscalers', probability: 'Medium', impact: 'Medium', mitigation: 'CUDA ecosystem moat' },
  { risk: 'Valuation compression on earnings deceleration', probability: 'Low', impact: 'High', mitigation: 'Covered by growth trajectory' },
];

const catalysts = [
  { event: 'Q1 FY2027 Earnings', date: '2026-05-28', expectedImpact: 'Positive', notes: 'Blackwell revenue ramp visibility' },
  { event: 'GTC Conference', date: '2026-03-17', expectedImpact: 'Positive', notes: 'New product announcements' },
  { event: 'MSFT/AMZN CapEx Guidance', date: '2026-04-25', expectedImpact: 'Positive', notes: 'Confirms demand runway' },
  { event: 'China Policy Update', date: 'TBD', expectedImpact: 'Uncertain', notes: 'Could restrict $4B+ revenue' },
];

const upside = ((thesis.targetPrice - thesis.currentPrice) / thesis.currentPrice * 100).toFixed(1);

export default function ThesisBuilder() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{thesis.ticker}</span>
        <span style={labelStyle}>{thesis.name}</span>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-signal-positive)', background: 'var(--color-surface-overlay)', padding: '2px 8px', borderRadius: '3px' }}>{thesis.direction} &mdash; {thesis.conviction}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>Target: ${thesis.targetPrice} (+{upside}%)</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Key Drivers</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Driver', 'Weight', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Driver' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {keyDrivers.map((d) => (
                <tr key={d.driver} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.driver}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.weight}%</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status.includes('Above') ? 'var(--color-signal-positive)' : d.status.includes('Ahead') ? 'var(--color-signal-warning)' : 'var(--color-text-secondary)' }}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Assessment</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Risk', 'Prob', 'Impact'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Risk' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {risks.map((r) => (
                <tr key={r.risk} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <div>{r.risk}</div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Mitigation: {r.mitigation}</div>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.probability === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.probability}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.impact === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.impact}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Catalyst Calendar</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'Event', 'Expected Impact', 'Notes'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Event' || h === 'Notes' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {catalysts.map((c) => (
                <tr key={c.event} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.event}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.expectedImpact === 'Positive' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{c.expectedImpact}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
