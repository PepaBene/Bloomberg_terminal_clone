// ---------------------------------------------------------------------------
// FI Intelligence — Cross-Asset Signals, Fallen Angel Watch, Issuance Intel
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

const crossAssetSignals = [
  { signal: 'Equity-Credit Divergence', direction: 'Bearish', strength: 7.2, asset: 'CDX HY', detail: 'HY spreads lagging equity selloff' },
  { signal: 'Rate Vol vs Credit Vol', direction: 'Neutral', strength: 5.0, asset: 'MOVE / CDX', detail: 'Rate vol elevated but credit vol contained' },
  { signal: 'EM Sovereign Stress', direction: 'Bullish', strength: 3.8, asset: 'EMBI+', detail: 'EM spreads tightening on USD weakness' },
  { signal: 'Curve-Credit Regime', direction: 'Bearish', strength: 6.5, asset: '2s10s / IG', detail: 'Curve steepening with IG widening' },
];

const fallenAngelWatch = [
  { issuer: 'Ford Motor Co', ticker: 'F', rating: 'BBB-', outlook: 'Negative', probability: 28, debt: '$98.2B', trigger: 'Leverage above 4x for 2 quarters' },
  { issuer: 'Kraft Heinz Co', ticker: 'KHC', rating: 'BBB-', outlook: 'Stable', probability: 15, debt: '$20.1B', trigger: 'FCF/Debt below 15%' },
  { issuer: 'Occidental Petroleum', ticker: 'OXY', rating: 'BBB-', outlook: 'Stable', probability: 12, debt: '$18.5B', trigger: 'Oil below $55 sustained' },
];

const issuanceIntel = [
  { issuer: 'Microsoft Corp', size: '$5.0B', tenor: '5Y/10Y/30Y', spread: 'T+55/70/90', status: 'Priced', date: '2026-03-25' },
  { issuer: 'JPMorgan Chase', size: '$3.5B', tenor: '6NC5', spread: 'T+95', status: 'Priced', date: '2026-03-24' },
  { issuer: 'Amazon.com', size: '$4.0B', tenor: '7Y/12Y', spread: 'Talk T+65/85', status: 'Pipeline', date: '2026-03-28' },
  { issuer: 'UnitedHealth Grp', size: '$2.5B', tenor: '10Y', spread: 'Talk T+80', status: 'Pipeline', date: '2026-03-28' },
];

// --- Component ---------------------------------------------------------------

export default function FIIntelligence() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Cross-asset signals, downgrade watchlist, and issuance intelligence</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Cross-Asset Signals */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Cross-Asset Signals</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {crossAssetSignals.map((s) => (
              <div key={s.signal} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{s.signal}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: s.direction === 'Bearish' ? 'var(--color-signal-negative)' : s.direction === 'Bullish' ? 'var(--color-signal-positive)' : 'var(--color-text-secondary)' }}>{s.direction}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{s.detail}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)' }}>Strength: {s.strength.toFixed(1)}/10</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Fallen Angel Watch */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Fallen Angel Watch</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Issuer', 'Rating', 'Outlook', 'Prob %', 'Debt'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fallenAngelWatch.map((f) => (
                <tr key={f.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <div style={{ fontWeight: 500 }}>{f.issuer}</div>
                    <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{f.trigger}</div>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-warning)' }}>{f.rating}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.outlook === 'Negative' ? 'var(--color-signal-negative)' : 'var(--color-text-secondary)' }}>{f.outlook}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{f.probability}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.debt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Issuance Intelligence */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Issuance Intelligence</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Issuer', 'Size', 'Tenor', 'Spread', 'Status'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {issuanceIntel.map((d) => (
                <tr key={d.issuer} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.size}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status === 'Priced' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
