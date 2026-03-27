// ---------------------------------------------------------------------------
// Watchlist View — Watchlist Management, Monitoring Alerts, Earnings Calendar
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };
function signalColor(v: number): string { return v >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)'; }

const watchlistItems = [
  { ticker: 'AAPL', name: 'Apple Inc.', price: 178.72, chg: -0.34, pe: 28.6, mktCap: '2.78T', alert: 'Earnings 4/25' },
  { ticker: 'MSFT', name: 'Microsoft Corp', price: 422.15, chg: 0.82, pe: 34.2, mktCap: '3.12T', alert: 'Earnings 4/22' },
  { ticker: 'NVDA', name: 'NVIDIA Corp', price: 878.36, chg: 4.82, pe: 62.5, mktCap: '2.18T', alert: 'Price > $875' },
  { ticker: 'GOOGL', name: 'Alphabet Inc.', price: 155.42, chg: 1.15, pe: 24.5, mktCap: '2.05T', alert: '' },
  { ticker: 'JPM', name: 'JPMorgan Chase', price: 195.80, chg: -0.52, pe: 11.8, mktCap: '$570B', alert: 'CDS widening' },
  { ticker: 'AMZN', name: 'Amazon.com', price: 182.50, chg: 0.95, pe: 58.3, mktCap: '1.92T', alert: '' },
  { ticker: 'META', name: 'Meta Platforms', price: 503.28, chg: 2.41, pe: 22.8, mktCap: '1.28T', alert: '' },
];

const earningsCalendar = [
  { date: '2026-04-15', ticker: 'JPM', name: 'JPMorgan Chase', time: 'BMO', epsEst: '$4.52', impliedMove: '3.2%' },
  { date: '2026-04-22', ticker: 'MSFT', name: 'Microsoft', time: 'AMC', epsEst: '$3.18', impliedMove: '4.5%' },
  { date: '2026-04-25', ticker: 'AAPL', name: 'Apple', time: 'AMC', epsEst: '$1.62', impliedMove: '3.8%' },
  { date: '2026-04-25', ticker: 'GOOGL', name: 'Alphabet', time: 'AMC', epsEst: '$1.89', impliedMove: '5.1%' },
  { date: '2026-04-30', ticker: 'AMZN', name: 'Amazon', time: 'AMC', epsEst: '$1.05', impliedMove: '6.2%' },
];

export default function WatchlistView() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Watchlist</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Core Holdings &mdash; 7 securities monitored</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Watchlist: Core Holdings</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Ticker', 'Name', 'Price', 'Chg %', 'P/E', 'Mkt Cap', 'Alert'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['Ticker', 'Name', 'Alert'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {watchlistItems.map((w) => (
                <tr key={w.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{w.ticker}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{w.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${w.price.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(w.chg), fontWeight: 500 }}>{w.chg >= 0 ? '+' : ''}{w.chg.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{w.pe.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${w.mktCap}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: w.alert ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{w.alert || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Upcoming Earnings</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'Ticker', 'Time', 'EPS Est', 'Impl. Move'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Ticker' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {earningsCalendar.map((e) => (
                <tr key={`${e.ticker}-${e.date}`} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{e.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{e.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{e.time}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.epsEst}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-warning)' }}>{e.impliedMove}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
