// ---------------------------------------------------------------------------
// Credit Profile — Ratings, Spread History, Debt Maturity, Covenants
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

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const ratings = [
  { agency: 'Moody\'s', rating: 'Aaa', outlook: 'Stable', lastAction: '2024-09-15' },
  { agency: 'S&P', rating: 'AA+', outlook: 'Stable', lastAction: '2024-07-22' },
  { agency: 'Fitch', rating: 'AA+', outlook: 'Stable', lastAction: '2024-08-10' },
];

const spreadHistory = [
  { date: '2026-03-27', spread: 42, zSpread: 48, asw: 45 },
  { date: '2026-02-27', spread: 45, zSpread: 51, asw: 48 },
  { date: '2026-01-27', spread: 50, zSpread: 56, asw: 53 },
  { date: '2025-12-27', spread: 47, zSpread: 53, asw: 50 },
  { date: '2025-09-27', spread: 55, zSpread: 61, asw: 58 },
];

const debtMaturities = [
  { year: '2026', amount: 8.5, coupon: '2.050%' },
  { year: '2027', amount: 11.2, coupon: '2.375%' },
  { year: '2028', amount: 9.8, coupon: '2.850%' },
  { year: '2029', amount: 7.4, coupon: '3.000%' },
  { year: '2030+', amount: 68.3, coupon: '3.450% avg' },
];

const covenants = [
  { covenant: 'Debt / EBITDA Max', threshold: '4.0x', current: '0.4x', headroom: '3.6x', status: 'Pass' },
  { covenant: 'Interest Coverage Min', threshold: '3.0x', current: '29.3x', headroom: '26.3x', status: 'Pass' },
  { covenant: 'Secured Debt Limit', threshold: '$20.0B', current: '$0.0B', headroom: '$20.0B', status: 'Pass' },
  { covenant: 'Restricted Payments', threshold: 'Builder basket', current: 'N/A', headroom: 'N/A', status: 'Pass' },
];

const creditMetrics = [
  { label: 'Total Debt', value: '$105.2B' },
  { label: 'Net Debt', value: '$48.6B' },
  { label: 'LTM EBITDA', value: '$130.8B' },
  { label: 'Net Leverage', value: '0.37x' },
  { label: 'FCF / Debt', value: '98.2%' },
  { label: 'CDS 5Y', value: '32 bps' },
];

// --- Component ---------------------------------------------------------------

export default function CreditProfile() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Credit Profile
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {creditMetrics.map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Credit Ratings */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Credit Ratings</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Agency', 'Rating', 'Outlook', 'Last Action'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ratings.map((r) => (
                <tr key={r.agency} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.agency}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{r.rating}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)' }}>{r.outlook}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.lastAction}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Spread History */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Spread History (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'OAS', 'Z-Spread', 'ASW'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spreadHistory.map((s) => (
                <tr key={s.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{s.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.zSpread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.asw}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Debt Maturity Wall */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Debt Maturity Wall ($B)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Year', 'Amount', 'Wt Avg Coupon', 'Bar'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Year' ? 'left' : h === 'Bar' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {debtMaturities.map((d) => (
                <tr key={d.year} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.year}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.amount.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.coupon}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)', width: '30%' }}>
                    <div style={{ height: '12px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                      <div style={{ height: '100%', width: `${(d.amount / 70) * 100}%`, background: 'var(--color-accent-primary)', borderRadius: '2px' }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Covenant Analysis */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Covenant Analysis</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Covenant', 'Threshold', 'Current', 'Headroom', 'Status'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Covenant' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {covenants.map((c) => (
                <tr key={c.covenant} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.covenant}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.threshold}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.current}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.headroom}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)', fontWeight: 500 }}>{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
