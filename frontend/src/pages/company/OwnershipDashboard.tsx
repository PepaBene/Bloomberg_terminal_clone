// ---------------------------------------------------------------------------
// Ownership Dashboard — Institutional Holders, Insider Ownership, Short Interest
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

const institutionalHolders = [
  { holder: 'Vanguard Group', shares: 1310000000, pctOut: 8.51, change: 12400000 },
  { holder: 'BlackRock Inc.', shares: 1010000000, pctOut: 6.56, change: -8200000 },
  { holder: 'Berkshire Hathaway', shares: 905000000, pctOut: 5.88, change: 0 },
  { holder: 'State Street Corp', shares: 622000000, pctOut: 4.04, change: 3100000 },
  { holder: 'FMR LLC (Fidelity)', shares: 358000000, pctOut: 2.33, change: -15600000 },
];

const ownershipSummary = [
  { label: 'Institutional', value: '60.8%' },
  { label: 'Insider', value: '0.07%' },
  { label: 'Retail / Other', value: '39.13%' },
  { label: 'Shares Outstanding', value: '15.41B' },
  { label: 'Float', value: '15.40B' },
  { label: '# Institutions', value: '5,842' },
];

const shortInterest = [
  { date: '2026-03-15', shortShares: 112000000, pctFloat: 0.73, daysToCover: 1.2 },
  { date: '2026-02-28', shortShares: 119000000, pctFloat: 0.78, daysToCover: 1.3 },
  { date: '2026-02-14', shortShares: 107000000, pctFloat: 0.70, daysToCover: 1.1 },
  { date: '2026-01-31', shortShares: 125000000, pctFloat: 0.82, daysToCover: 1.4 },
];

function fmtShares(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString();
}

// --- Component ---------------------------------------------------------------

export default function OwnershipDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Ownership Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      {/* Summary Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {ownershipSummary.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Top Institutional Holders */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Top Institutional Holders</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Holder', 'Shares', '% Outstanding', 'Qtr Change'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Holder' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {institutionalHolders.map((h) => (
                <tr key={h.holder} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{h.holder}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtShares(h.shares)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{h.pctOut.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: h.change > 0 ? 'var(--color-signal-positive)' : h.change < 0 ? 'var(--color-signal-negative)' : 'var(--color-text-secondary)' }}>
                    {h.change === 0 ? 'Unch' : `${h.change > 0 ? '+' : ''}${fmtShares(h.change)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Short Interest */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Short Interest</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Short', '% Float', 'DTC'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shortInterest.map((s) => (
                <tr key={s.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{s.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtShares(s.shortShares)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.pctFloat.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.daysToCover.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
