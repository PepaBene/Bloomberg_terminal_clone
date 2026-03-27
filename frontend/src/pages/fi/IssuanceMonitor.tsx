// ---------------------------------------------------------------------------
// Issuance Monitor — New Issue Calendar, Pipeline, Pricing vs Talk
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

const weeklyStats = [
  { label: 'IG Volume (WTD)', value: '$28.5B' },
  { label: 'HY Volume (WTD)', value: '$8.2B' },
  { label: 'IG Avg NIC', value: '-2 bps' },
  { label: 'HY Avg NIC', value: '+5 bps' },
  { label: 'Deals Priced', value: '18' },
  { label: 'Pipeline', value: '6 deals' },
];

const recentDeals = [
  { date: '2026-03-26', issuer: 'Microsoft Corp', rating: 'AAA', size: 5000, tenor: '5Y', coupon: '3.750%', spread: 'T+55', nic: -3, book: '4.2x' },
  { date: '2026-03-26', issuer: 'JPMorgan Chase', rating: 'A+', size: 3500, tenor: '6NC5', coupon: '4.875%', spread: 'T+95', nic: 0, book: '3.1x' },
  { date: '2026-03-25', issuer: 'UnitedHealth', rating: 'A+', size: 2500, tenor: '10Y', coupon: '4.250%', spread: 'T+78', nic: -2, book: '3.8x' },
  { date: '2026-03-25', issuer: 'Comcast Corp', rating: 'A-', size: 2000, tenor: '30Y', coupon: '5.125%', spread: 'T+115', nic: 3, book: '2.5x' },
  { date: '2026-03-24', issuer: 'Oracle Corp', rating: 'BBB', size: 4000, tenor: '10Y/30Y', coupon: '4.750%', spread: 'T+125', nic: 5, book: '2.8x' },
];

const pipeline = [
  { issuer: 'Amazon.com', rating: 'AA', estSize: '$4.0B', tenor: '7Y/12Y', talk: 'T+65/85', expected: '2026-03-28' },
  { issuer: 'Goldman Sachs', rating: 'A+', estSize: '$3.0B', tenor: '11NC10', talk: 'T+110', expected: '2026-03-28' },
  { issuer: 'Pfizer Inc', rating: 'A-', estSize: '$2.5B', tenor: '5Y/10Y', talk: 'T+70/95', expected: '2026-03-31' },
  { issuer: 'T-Mobile US', rating: 'BBB+', estSize: '$2.0B', tenor: '10Y', talk: 'T+105', expected: '2026-03-31' },
];

// --- Component ---------------------------------------------------------------

export default function IssuanceMonitor() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          New Issue Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Primary market activity, pipeline, and pricing analysis</p>
      </div>

      {/* Weekly Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {weeklyStats.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {/* Recent Deals */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Recently Priced</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Issuer', 'Rating', 'Size ($M)', 'Tenor', 'Coupon', 'Spread', 'NIC', 'Book'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: ['Issuer'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentDeals.map((d, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{d.rating}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.size.toLocaleString()}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.coupon}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.nic <= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{d.nic > 0 ? '+' : ''}{d.nic}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.book}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pipeline */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Pipeline</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Expected', 'Issuer', 'Rating', 'Est. Size', 'Tenor', 'IPT / Talk'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pipeline.map((p) => (
                <tr key={p.issuer} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{p.expected}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{p.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{p.rating}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.estSize}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-warning)' }}>{p.talk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
