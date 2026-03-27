// ---------------------------------------------------------------------------
// Morning Brief — Landing Page
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

function signalColor(value: number): string {
  return value >= 0
    ? 'var(--color-signal-positive)'
    : 'var(--color-signal-negative)';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatPrice(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// --- Mock Data ---------------------------------------------------------------

interface MarketIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

const marketIndices: MarketIndex[] = [
  { name: 'S&P 500',      value: 5248.72, change: 18.34,   changePct: 0.35 },
  { name: 'DJIA',         value: 39142.50, change: -42.18, changePct: -0.11 },
  { name: 'NASDAQ',       value: 16432.85, change: 87.62,  changePct: 0.54 },
  { name: '10Y Treasury', value: 4.278,    change: -0.032, changePct: -0.74 },
];

interface TopMover {
  ticker: string;
  name: string;
  price: number;
  changePct: number;
}

const topMovers: TopMover[] = [
  { ticker: 'NVDA', name: 'NVIDIA Corp',      price: 878.36, changePct: 4.82 },
  { ticker: 'SMCI', name: 'Super Micro Comp',  price: 932.10, changePct: 3.67 },
  { ticker: 'META', name: 'Meta Platforms',     price: 503.28, changePct: 2.41 },
  { ticker: 'INTC', name: 'Intel Corp',         price: 31.42,  changePct: -4.15 },
  { ticker: 'PFE',  name: 'Pfizer Inc',         price: 26.88,  changePct: -3.28 },
];

interface AlertItem {
  id: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  time: string;
}

const recentAlerts: AlertItem[] = [
  { id: '1', severity: 'high',   title: 'AAPL — Earnings miss: EPS $1.52 vs est. $1.58',       time: '08:32' },
  { id: '2', severity: 'medium', title: 'UST 10Y yield breached 4.30% level',                   time: '09:15' },
  { id: '3', severity: 'low',    title: 'MSFT — New insider purchase filed (Form 4)',            time: '10:02' },
  { id: '4', severity: 'medium', title: 'VIX spiked above 18 — elevated volatility regime',     time: '10:47' },
  { id: '5', severity: 'high',   title: 'JPM — CDS spread widened 12 bps in 24h',               time: '11:20' },
];

interface EconEvent {
  date: string;
  time: string;
  event: string;
  forecast: string;
  prior: string;
}

const econCalendar: EconEvent[] = [
  { date: '2026-03-27', time: '08:30', event: 'Initial Jobless Claims',        forecast: '212K', prior: '209K' },
  { date: '2026-03-27', time: '10:00', event: 'Pending Home Sales MoM',        forecast: '1.5%', prior: '-4.9%' },
  { date: '2026-03-28', time: '08:30', event: 'Core PCE Price Index YoY',      forecast: '2.8%', prior: '2.8%' },
  { date: '2026-03-28', time: '10:00', event: 'Michigan Consumer Sentiment',   forecast: '76.5', prior: '76.9' },
  { date: '2026-03-31', time: '09:45', event: 'Chicago PMI',                   forecast: '46.0', prior: '44.0' },
  { date: '2026-03-31', time: '10:30', event: 'Dallas Fed Manufacturing',      forecast: '-8.0', prior: '-11.3' },
];

// --- Severity badge color ---
function severityColor(s: AlertItem['severity']): string {
  switch (s) {
    case 'high':   return 'var(--color-signal-negative)';
    case 'medium': return 'var(--color-signal-warning)';
    case 'low':    return 'var(--color-signal-neutral)';
  }
}

// --- Component ---------------------------------------------------------------

export default function MorningBrief() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Morning Brief
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Thursday, March 27 2026 &mdash; Markets &amp; Intelligence Summary
        </p>
      </div>

      {/* 2-column golden ratio grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* ---- LEFT COLUMN (65%) ---- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Market Overview */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Market Overview</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Index', 'Last', 'Change', '% Chg'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Index' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {marketIndices.map((idx) => (
                  <tr key={idx.name} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{idx.name}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatPrice(idx.value)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(idx.change) }}>
                      {idx.change >= 0 ? '+' : ''}{idx.change.toFixed(2)}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(idx.changePct) }}>
                      {formatPct(idx.changePct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Top Movers */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Top Movers</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Ticker', 'Name', 'Price', '% Change'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Ticker' || h === 'Name' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topMovers.map((m) => (
                  <tr key={m.ticker} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{m.ticker}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{m.name}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${formatPrice(m.price)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(m.changePct), fontWeight: 500 }}>
                      {formatPct(m.changePct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Economic Calendar */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Economic Calendar</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Time', 'Event', 'Forecast', 'Prior'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Event' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {econCalendar.map((ev, i) => (
                  <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ev.date}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ev.time}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ev.event}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ev.forecast}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>{ev.prior}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ---- RIGHT COLUMN (35%) ---- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Alerts */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Alerts</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentAlerts.map((a) => (
                <div key={a.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span style={{
                    display: 'inline-block',
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: severityColor(a.severity),
                    marginTop: '5px',
                    flexShrink: 0,
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>
                      {a.title}
                    </div>
                    <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                      {a.time}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
