// ---------------------------------------------------------------------------
// Flows Dashboard — Institutional Flows, 13F Filings, Whale Trades
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const flowKPIs = [
  { label: 'Equity Fund Flows (WTD)', value: '+$4.2B' },
  { label: 'Bond Fund Flows (WTD)', value: '+$8.7B' },
  { label: 'Money Market', value: '+$12.1B' },
  { label: 'ETF Inflows (MTD)', value: '+$32.5B' },
  { label: '13F Season', value: 'Active' },
  { label: 'Whale Alerts', value: '7' },
];

const whaleTrades = [
  { date: '2026-03-25', fund: 'Berkshire Hathaway', action: 'Buy', ticker: 'OXY', shares: '12.5M', estValue: '$685M' },
  { date: '2026-03-22', fund: 'Bridgewater', action: 'Sell', ticker: 'SPY', shares: '4.2M', estValue: '$2.2B' },
  { date: '2026-03-20', fund: 'Citadel', action: 'Buy', ticker: 'TSLA', shares: '2.8M', estValue: '$504M' },
  { date: '2026-03-18', fund: 'Renaissance Tech', action: 'Buy', ticker: 'NVDA', shares: '1.5M', estValue: '$1.32B' },
  { date: '2026-03-15', fund: 'Soros Fund Mgmt', action: 'Sell', ticker: 'META', shares: '800K', estValue: '$402M' },
];

const sectorRotation = [
  { sector: 'Technology', inflows: 8.2, outflows: -2.1, net: 6.1 },
  { sector: 'Health Care', inflows: 3.5, outflows: -1.8, net: 1.7 },
  { sector: 'Financials', inflows: 4.1, outflows: -3.2, net: 0.9 },
  { sector: 'Energy', inflows: 1.2, outflows: -2.8, net: -1.6 },
  { sector: 'Consumer Staples', inflows: 0.8, outflows: -2.1, net: -1.3 },
  { sector: 'Real Estate', inflows: 0.5, outflows: -1.8, net: -1.3 },
];

export default function FlowsDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Institutional Flows</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Fund flows, sector rotation, 13F activity, and whale alerts</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {flowKPIs.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: k.value.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Whale Trades</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'Fund', 'Action', 'Ticker', 'Shares', 'Est. Value'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['Fund'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {whaleTrades.map((t, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{t.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{t.fund}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: t.action === 'Buy' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>{t.action}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{t.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.shares}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{t.estValue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Sector Rotation ($B, MTD)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Sector', 'Inflows', 'Outflows', 'Net'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Sector' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {sectorRotation.map((s) => (
                <tr key={s.sector} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sector}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)' }}>+{s.inflows.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{s.outflows.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: s.net >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{s.net >= 0 ? '+' : ''}{s.net.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
