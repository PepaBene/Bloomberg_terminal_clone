// ---------------------------------------------------------------------------
// Treasury Dashboard — Yield Curve, Auction Results, Rate Sensitivity
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

function chgColor(v: number): string {
  return v >= 0 ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)';
}

// --- Mock Data ---------------------------------------------------------------

const curveData = [
  { tenor: '1M', yield: 5.31, chg: -0.01 },
  { tenor: '3M', yield: 5.28, chg: -0.02 },
  { tenor: '6M', yield: 5.12, chg: -0.03 },
  { tenor: '1Y', yield: 4.85, chg: -0.05 },
  { tenor: '2Y', yield: 4.52, chg: -0.04 },
  { tenor: '5Y', yield: 4.18, chg: -0.03 },
  { tenor: '10Y', yield: 4.28, chg: -0.03 },
  { tenor: '30Y', yield: 4.52, chg: -0.02 },
];

const keySpreads = [
  { label: '2s10s', value: -24, chg: 1 },
  { label: '2s30s', value: 0, chg: 2 },
  { label: '5s30s', value: 34, chg: 1 },
  { label: '10Y TIPS BE', value: 2.32, chg: -0.01 },
  { label: '10Y Real', value: 1.96, chg: -0.02 },
  { label: 'Fed Funds', value: 5.33, chg: 0 },
];

const auctionResults = [
  { date: '2026-03-25', security: '2Y Note', size: '$48B', highYield: '4.520%', bidCover: 2.68, tail: '0.2 bps', indirect: '72.5%' },
  { date: '2026-03-26', security: '5Y Note', size: '$49B', highYield: '4.180%', bidCover: 2.45, tail: '-0.1 bps', indirect: '68.2%' },
  { date: '2026-03-27', security: '7Y Note', size: '$41B', highYield: '4.250%', bidCover: 2.52, tail: '0.5 bps', indirect: '70.1%' },
];

const rateSensitivity = [
  { scenario: '+100 bps parallel', duration: -6.2, convexity: 0.3, pnl: '-$6.2M' },
  { scenario: '-100 bps parallel', duration: 6.2, convexity: 0.3, pnl: '+$6.5M' },
  { scenario: 'Bear steepener', duration: -2.1, convexity: 0.1, pnl: '-$2.0M' },
  { scenario: 'Bull flattener', duration: 3.8, convexity: 0.2, pnl: '+$4.0M' },
];

// --- Component ---------------------------------------------------------------

export default function TreasuryDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Treasury Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>UST curve, key spreads, auction results, and rate sensitivity</p>
      </div>

      {/* Key Spreads KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {keySpreads.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              {typeof s.value === 'number' && s.value % 1 === 0 ? `${s.value} bps` : `${s.value}%`}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Treasury Curve */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Treasury Yield Curve</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Tenor', 'Yield', 'Chg (bps)'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {curveData.map((c) => (
                <tr key={c.tenor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.yield.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(c.chg) }}>
                    {c.chg > 0 ? '+' : ''}{(c.chg * 100).toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Rate Sensitivity */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Rate Sensitivity Analysis</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Scenario', 'Duration', 'Convexity', 'P&L Impact'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Scenario' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rateSensitivity.map((r) => (
                <tr key={r.scenario} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.scenario}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.duration.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.convexity.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: r.pnl.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{r.pnl}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Auction Results */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Recent Auction Results</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Security', 'Size', 'High Yield', 'Bid/Cover', 'Tail', 'Indirect %'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: ['Security'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {auctionResults.map((a) => (
                <tr key={a.security} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{a.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{a.security}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.size}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{a.highYield}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.bidCover.toFixed(2)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.tail}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.indirect}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
