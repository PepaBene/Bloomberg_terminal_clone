// ---------------------------------------------------------------------------
// Equity Screener Dashboard
// ---------------------------------------------------------------------------
import { useState } from 'react';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
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

const selectStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: '4px 8px',
  outline: 'none',
};

const inputStyle: React.CSSProperties = {
  ...selectStyle,
  width: '72px',
  fontFamily: 'var(--font-data)',
};

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function qualityColor(score: number): string {
  if (score >= 8) return 'var(--color-quality-5)';
  if (score >= 6) return 'var(--color-quality-4)';
  if (score >= 4) return 'var(--color-quality-3)';
  if (score >= 2) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

function formatCap(b: number): string {
  if (b >= 1000) return `$${(b / 1000).toFixed(1)}T`;
  if (b >= 1) return `$${b.toFixed(1)}B`;
  return `$${(b * 1000).toFixed(0)}M`;
}

// --- Mock Data ---------------------------------------------------------------

interface ScreenerRow {
  ticker: string;
  name: string;
  sector: string;
  marketCapB: number;
  pe: number;
  roe: number;
  revGrowth: number;
  piotroski: number;
}

const mockStocks: ScreenerRow[] = [
  { ticker: 'AAPL',  name: 'Apple Inc.',           sector: 'Technology',      marketCapB: 2780, pe: 28.6,  roe: 156.8, revGrowth: 5.2,  piotroski: 7 },
  { ticker: 'MSFT',  name: 'Microsoft Corp.',      sector: 'Technology',      marketCapB: 3120, pe: 35.2,  roe: 39.4,  revGrowth: 12.8, piotroski: 8 },
  { ticker: 'NVDA',  name: 'NVIDIA Corp.',         sector: 'Technology',      marketCapB: 2180, pe: 62.4,  roe: 92.3,  revGrowth: 122.4, piotroski: 8 },
  { ticker: 'AMZN',  name: 'Amazon.com Inc.',      sector: 'Consumer Disc.',  marketCapB: 1890, pe: 42.1,  roe: 22.8,  revGrowth: 13.2, piotroski: 6 },
  { ticker: 'GOOGL', name: 'Alphabet Inc.',        sector: 'Technology',      marketCapB: 1960, pe: 24.3,  roe: 28.1,  revGrowth: 15.4, piotroski: 7 },
  { ticker: 'META',  name: 'Meta Platforms',        sector: 'Technology',      marketCapB: 1280, pe: 26.8,  roe: 33.6,  revGrowth: 24.6, piotroski: 7 },
  { ticker: 'BRK.B', name: 'Berkshire Hathaway',   sector: 'Financials',      marketCapB: 890,  pe: 8.4,   roe: 14.2,  revGrowth: 2.8,  piotroski: 5 },
  { ticker: 'JPM',   name: 'JPMorgan Chase',       sector: 'Financials',      marketCapB: 580,  pe: 12.1,  roe: 16.8,  revGrowth: 8.4,  piotroski: 6 },
  { ticker: 'UNH',   name: 'UnitedHealth Group',   sector: 'Healthcare',      marketCapB: 490,  pe: 22.4,  roe: 25.6,  revGrowth: 14.2, piotroski: 7 },
  { ticker: 'V',     name: 'Visa Inc.',            sector: 'Financials',      marketCapB: 560,  pe: 30.8,  roe: 44.2,  revGrowth: 10.6, piotroski: 8 },
  { ticker: 'LLY',   name: 'Eli Lilly & Co.',      sector: 'Healthcare',      marketCapB: 740,  pe: 118.2, roe: 58.4,  revGrowth: 32.4, piotroski: 6 },
  { ticker: 'XOM',   name: 'Exxon Mobil Corp.',    sector: 'Energy',          marketCapB: 480,  pe: 12.8,  roe: 18.2,  revGrowth: -4.8, piotroski: 5 },
  { ticker: 'PG',    name: 'Procter & Gamble',     sector: 'Consumer Stap.',  marketCapB: 380,  pe: 26.4,  roe: 32.1,  revGrowth: 3.2,  piotroski: 6 },
  { ticker: 'HD',    name: 'Home Depot Inc.',       sector: 'Consumer Disc.',  marketCapB: 362,  pe: 24.8,  roe: -1280, revGrowth: 2.8,  piotroski: 4 },
  { ticker: 'COST',  name: 'Costco Wholesale',     sector: 'Consumer Stap.',  marketCapB: 340,  pe: 50.2,  roe: 28.4,  revGrowth: 9.8,  piotroski: 7 },
  { ticker: 'ABBV',  name: 'AbbVie Inc.',          sector: 'Healthcare',      marketCapB: 310,  pe: 18.2,  roe: -42.1, revGrowth: -6.2, piotroski: 4 },
  { ticker: 'CRM',   name: 'Salesforce Inc.',      sector: 'Technology',      marketCapB: 268,  pe: 42.6,  roe: 10.8,  revGrowth: 11.4, piotroski: 5 },
  { ticker: 'NFLX',  name: 'Netflix Inc.',         sector: 'Technology',      marketCapB: 252,  pe: 38.4,  roe: 26.2,  revGrowth: 16.8, piotroski: 7 },
  { ticker: 'AMD',   name: 'Advanced Micro Dev.',  sector: 'Technology',      marketCapB: 244,  pe: 46.8,  roe: 4.2,   revGrowth: 18.2, piotroski: 5 },
  { ticker: 'CAT',   name: 'Caterpillar Inc.',     sector: 'Industrials',     marketCapB: 178,  pe: 16.2,  roe: 54.8,  revGrowth: -2.4, piotroski: 6 },
];

const sectors = ['All Sectors', 'Technology', 'Financials', 'Healthcare', 'Consumer Disc.', 'Consumer Stap.', 'Energy', 'Industrials'];

// --- Component ---------------------------------------------------------------

export default function ScreenerDashboard() {
  const [sector, setSector] = useState('All Sectors');
  const [peMin, setPeMin] = useState('');
  const [peMax, setPeMax] = useState('');
  const [roeMin, setRoeMin] = useState('');
  const [capFilter, setCapFilter] = useState('All');

  const filtered = mockStocks.filter((s) => {
    if (sector !== 'All Sectors' && s.sector !== sector) return false;
    if (peMin && s.pe < Number(peMin)) return false;
    if (peMax && s.pe > Number(peMax)) return false;
    if (roeMin && s.roe < Number(roeMin)) return false;
    if (capFilter === 'Large' && s.marketCapB < 100) return false;
    if (capFilter === 'Mega' && s.marketCapB < 500) return false;
    return true;
  });

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Equity Screener
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {filtered.length} results matching filters
        </p>
      </div>

      {/* Filter Bar */}
      <div style={{
        ...panelStyle,
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        flexWrap: 'wrap',
        marginBottom: 'var(--panel-gap)',
        padding: '8px 12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Sector</span>
          <select style={selectStyle} value={sector} onChange={(e) => setSector(e.target.value)}>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Market Cap</span>
          <select style={selectStyle} value={capFilter} onChange={(e) => setCapFilter(e.target.value)}>
            <option value="All">All</option>
            <option value="Mega">Mega (&gt;$500B)</option>
            <option value="Large">Large (&gt;$100B)</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>P/E</span>
          <input style={inputStyle} placeholder="Min" value={peMin} onChange={(e) => setPeMin(e.target.value)} />
          <span style={{ color: 'var(--color-text-tertiary)' }}>&ndash;</span>
          <input style={inputStyle} placeholder="Max" value={peMax} onChange={(e) => setPeMax(e.target.value)} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>ROE Min</span>
          <input style={inputStyle} placeholder="%" value={roeMin} onChange={(e) => setRoeMin(e.target.value)} />
        </div>
      </div>

      {/* Results Table */}
      <div style={panelStyle}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Ticker', 'Name', 'Sector', 'Market Cap', 'P/E', 'ROE', 'Rev Growth', 'Piotroski'].map((h) => (
                <th
                  key={h}
                  style={{
                    ...labelStyle,
                    textAlign: h === 'Ticker' || h === 'Name' || h === 'Sector' ? 'left' : 'right',
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
            {filtered.map((s) => (
              <tr key={s.ticker} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{s.ticker}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{s.name}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sector}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatCap(s.marketCapB)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.pe.toFixed(1)}x</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.roe) }}>{s.roe.toFixed(1)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.revGrowth) }}>
                  {s.revGrowth >= 0 ? '+' : ''}{s.revGrowth.toFixed(1)}%
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: qualityColor(s.piotroski), fontWeight: 600 }}>
                  {s.piotroski}/9
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
