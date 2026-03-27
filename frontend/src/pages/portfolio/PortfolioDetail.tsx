// ---------------------------------------------------------------------------
// Portfolio Detail — Single Portfolio View
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { DonutChart, TimeSeriesChart } from '@/components/charts';

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
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

// --- Mock Data ---------------------------------------------------------------

const portfolio = {
  name: 'Core Growth',
  nav: 2_458_320,
  dayChange: 0.34,
  dayChangeDollar: 8_358,
  inception: '2024-01-15',
};

interface Holding {
  ticker: string;
  name: string;
  shares: number;
  price: number;
  marketValue: number;
  weight: number;
  dayChange: number;
  unrealizedPnl: number;
}

const holdings: Holding[] = [
  { ticker: 'AAPL',  name: 'Apple Inc.',           shares: 450,  price: 178.72, marketValue: 80_424,  weight: 3.27, dayChange: -0.34, unrealizedPnl: 12_480 },
  { ticker: 'MSFT',  name: 'Microsoft Corp.',      shares: 320,  price: 415.60, marketValue: 132_992, weight: 5.41, dayChange: 0.52,  unrealizedPnl: 28_640 },
  { ticker: 'NVDA',  name: 'NVIDIA Corp.',         shares: 200,  price: 878.36, marketValue: 175_672, weight: 7.15, dayChange: 4.82,  unrealizedPnl: 62_340 },
  { ticker: 'AMZN',  name: 'Amazon.com Inc.',      shares: 380,  price: 182.45, marketValue: 69_331,  weight: 2.82, dayChange: 1.12,  unrealizedPnl: 8_920 },
  { ticker: 'GOOGL', name: 'Alphabet Inc.',        shares: 420,  price: 155.28, marketValue: 65_218,  weight: 2.65, dayChange: -0.18, unrealizedPnl: 5_460 },
  { ticker: 'META',  name: 'Meta Platforms',        shares: 180,  price: 503.28, marketValue: 90_590,  weight: 3.69, dayChange: 2.41,  unrealizedPnl: 18_720 },
  { ticker: 'JPM',   name: 'JPMorgan Chase',       shares: 500,  price: 198.42, marketValue: 99_210,  weight: 4.04, dayChange: -0.62, unrealizedPnl: 14_350 },
  { ticker: 'UNH',   name: 'UnitedHealth Group',   shares: 120,  price: 528.90, marketValue: 63_468,  weight: 2.58, dayChange: 0.28,  unrealizedPnl: 7_240 },
  { ticker: 'V',     name: 'Visa Inc.',            shares: 280,  price: 278.15, marketValue: 77_882,  weight: 3.17, dayChange: 0.45,  unrealizedPnl: 9_680 },
  { ticker: 'LLY',   name: 'Eli Lilly & Co.',      shares: 90,   price: 782.50, marketValue: 70_425,  weight: 2.87, dayChange: 1.78,  unrealizedPnl: 22_150 },
];

interface PerformanceMetric {
  label: string;
  value: string;
}

const perfMetrics: PerformanceMetric[] = [
  { label: 'TWR (YTD)',      value: '+8.42%' },
  { label: 'Sharpe Ratio',   value: '1.34' },
  { label: 'Max Drawdown',   value: '-6.18%' },
  { label: 'Beta (vs SPX)',  value: '1.12' },
];

// --- Sector Allocation Data --------------------------------------------------

const SECTOR_ALLOCATION = [
  { name: 'Technology', value: 32.4 },
  { name: 'Healthcare', value: 14.8 },
  { name: 'Financials', value: 12.6 },
  { name: 'Consumer Disc.', value: 11.2 },
  { name: 'Communication', value: 9.8 },
  { name: 'Industrials', value: 7.4 },
  { name: 'Other', value: 11.8 },
];

// --- NAV History (30 days) ---------------------------------------------------

function generateNavHistory(): { date: string; value: number }[] {
  const data: { date: string; value: number }[] = [];
  let nav = 10_000_000;
  const start = new Date('2026-02-25');
  for (let i = 0; i < 30; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const dailyReturn = (Math.random() - 0.47) * 0.012;
    nav *= 1 + dailyReturn;
    data.push({ date: d.toISOString().slice(0, 10), value: Math.round(nav) });
  }
  return data;
}

function NavHistoryChart() {
  const data = useMemo(() => generateNavHistory(), []);
  return (
    <TimeSeriesChart
      data={data}
      height={200}
      showGrid
      series={[{ key: 'value', color: '#3B82F6', name: 'NAV', type: 'area' }]}
      yAxisFormat={(v: number) => `$${(v / 1_000_000).toFixed(2)}M`}
    />
  );
}

// --- Component ---------------------------------------------------------------

export default function PortfolioDetail() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '16px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {portfolio.name}
        </h1>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            {formatCurrency(portfolio.nav)}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-md)', color: signalColor(portfolio.dayChange) }}>
            {formatPct(portfolio.dayChange)} ({portfolio.dayChangeDollar >= 0 ? '+' : ''}{formatCurrency(portfolio.dayChangeDollar)})
          </span>
        </div>
        <span style={{ ...labelStyle }}>Inception: <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{portfolio.inception}</span></span>
      </div>

      {/* Performance Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {perfMetrics.map((m) => (
          <div key={m.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{m.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: m.value.startsWith('-') ? 'var(--color-signal-negative)' : m.value.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-text-primary)' }}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left — Holdings Table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Holdings</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Ticker', 'Name', 'Shares', 'Price', 'Mkt Value', 'Weight', 'Day Chg', 'Unreal. P&L'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: h === 'Ticker' || h === 'Name' ? 'left' : 'right',
                      padding: 'var(--table-cell-py) var(--table-cell-px)',
                      borderBottom: '1px solid var(--color-surface-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{h.ticker}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{h.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{h.shares.toLocaleString()}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${h.price.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatCurrency(h.marketValue)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{h.weight.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(h.dayChange) }}>{formatPct(h.dayChange)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(h.unrealizedPnl) }}>{formatCurrency(h.unrealizedPnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right — Allocation + Summary */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Sector Allocation Donut */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Sector Allocation</h2>
            <DonutChart
              data={SECTOR_ALLOCATION}
              height={240}
              centerLabel="Sectors"
              centerValue="7"
              showLegend
            />
          </div>

          {/* NAV History (30 days) */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>NAV History (30D)</h2>
            <NavHistoryChart />
          </div>

          {/* Portfolio Summary */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Summary</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { label: 'Total Positions', value: String(holdings.length) },
                { label: 'Total Market Value', value: formatCurrency(holdings.reduce((s, h) => s + h.marketValue, 0)) },
                { label: 'Total Unrealized P&L', value: formatCurrency(holdings.reduce((s, h) => s + h.unrealizedPnl, 0)) },
                { label: 'Largest Position', value: `${holdings.reduce((max, h) => h.weight > max.weight ? h : max, holdings[0]!.weight > 0 ? holdings[0]! : holdings[0]!).ticker} (${holdings.reduce((max, h) => h.weight > max.weight ? h : max, holdings[0]!).weight.toFixed(1)}%)` },
              ].map((item) => (
                <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span style={labelStyle}>{item.label}</span>
                  <span style={dataStyle}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
