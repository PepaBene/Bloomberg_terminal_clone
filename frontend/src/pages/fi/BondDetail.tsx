// ---------------------------------------------------------------------------
// Bond Detail — Characteristics, Pricing, Yield Analysis, Call Schedule
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

const bond = {
  issuer: 'Apple Inc.',
  cusip: '037833DX3',
  coupon: '3.250%',
  maturity: '2029-02-23',
  rating: 'AA+ / Aaa',
  issueSize: '$2,000M',
  currency: 'USD',
  seniority: 'Senior Unsecured',
  couponFreq: 'Semi-Annual',
};

const pricing = [
  { label: 'Price', value: '101.450' },
  { label: 'Yield (YTM)', value: '2.872%' },
  { label: 'Yield (YTW)', value: '2.845%' },
  { label: 'OAS', value: '42 bps' },
  { label: 'Z-Spread', value: '48 bps' },
  { label: 'Modified Duration', value: '2.78' },
  { label: 'Convexity', value: '0.09' },
  { label: 'DV01', value: '$0.0278' },
];

const yieldHistory = [
  { date: '2026-03-27', price: 101.45, ytm: 2.872, oas: 42 },
  { date: '2026-02-27', price: 100.89, ytm: 2.985, oas: 45 },
  { date: '2026-01-27', price: 99.75, ytm: 3.128, oas: 51 },
  { date: '2025-12-27', price: 100.12, ytm: 3.052, oas: 48 },
  { date: '2025-09-27', price: 98.85, ytm: 3.312, oas: 58 },
];

const callSchedule = [
  { date: '2028-11-23', type: 'Make-Whole', price: 'T+15 bps' },
  { date: '2029-01-23', type: 'Par Call', price: '100.000' },
];

const comparables = [
  { issuer: 'MSFT 3.125% 2028', price: 100.82, ytm: 2.712, oas: 35, rating: 'AAA/Aaa' },
  { issuer: 'GOOGL 3.375% 2029', price: 101.10, ytm: 2.945, oas: 47, rating: 'AA+/Aa2' },
  { issuer: 'AMZN 3.600% 2029', price: 101.95, ytm: 3.015, oas: 52, rating: 'AA/Aa3' },
];

// --- Component ---------------------------------------------------------------

export default function BondDetail() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {bond.issuer} {bond.coupon} {bond.maturity.slice(0, 4)}
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>CUSIP: {bond.cusip} &mdash; {bond.rating} &mdash; {bond.seniority}</p>
      </div>

      {/* Pricing KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {pricing.slice(0, 4).map((p) => (
          <div key={p.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{p.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{p.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Bond Characteristics */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Bond Characteristics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {Object.entries(bond).map(([k, v]) => (
                <tr key={k} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', textTransform: 'capitalize' }}>{k.replace(/([A-Z])/g, ' $1')}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Risk Analytics */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Analytics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {pricing.slice(4).map((p) => (
                <tr key={p.label} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.label}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2 style={{ ...sectionTitle, marginTop: '16px' }}>Call Schedule</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Type', 'Price'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {callSchedule.map((c) => (
                <tr key={c.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.type}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.price}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Yield History */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Price / Yield History</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Price', 'YTM', 'OAS (bps)'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {yieldHistory.map((y) => (
                <tr key={y.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{y.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{y.price.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{y.ytm.toFixed(3)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{y.oas}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Comparable Bonds */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Comparable Bonds</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Bond', 'Price', 'YTM', 'OAS', 'Rating'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Bond' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparables.map((c) => (
                <tr key={c.issuer} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.price.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.ytm.toFixed(3)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.oas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{c.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
