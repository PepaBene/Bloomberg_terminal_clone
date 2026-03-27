// ---------------------------------------------------------------------------
// Equity Screener Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

// --- Helpers -----------------------------------------------------------------

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

// --- Skeleton ----------------------------------------------------------------

function Skeleton({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-sm)',
      }}
    />
  );
}

// --- Mock Data (fallback) ----------------------------------------------------

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

const MOCK_STOCKS: ScreenerRow[] = [
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

const SECTORS = ['All Sectors', 'Technology', 'Financials', 'Healthcare', 'Consumer Disc.', 'Consumer Stap.', 'Energy', 'Industrials'];

// --- Filter styles -----------------------------------------------------------

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

// --- Component ---------------------------------------------------------------

interface ScreenerFilters {
  sector: string;
  capFilter: string;
  peMin: string;
  peMax: string;
  roeMin: string;
}

export default function ScreenerDashboard() {
  const [filters, setFilters] = useState<ScreenerFilters>({
    sector: 'All Sectors',
    capFilter: 'All',
    peMin: '',
    peMax: '',
    roeMin: '',
  });

  // Fetch screener results from API
  const { data: apiStocks, isLoading } = useQuery<ScreenerRow[]>({
    queryKey: ['screener', 'results', filters],
    queryFn: () => api.get('/v4/screener/equity', {
      sector: filters.sector !== 'All Sectors' ? filters.sector : undefined,
      cap_filter: filters.capFilter !== 'All' ? filters.capFilter : undefined,
      pe_min: filters.peMin || undefined,
      pe_max: filters.peMax || undefined,
      roe_min: filters.roeMin || undefined,
    }),
    retry: 0,
  });
  const stocks = apiStocks ?? MOCK_STOCKS;

  // Apply client-side filters to fallback data (API should already filter, but mock needs it)
  const filtered = useMemo(() => {
    if (apiStocks) return apiStocks; // API already filtered
    return stocks.filter((s) => {
      if (filters.sector !== 'All Sectors' && s.sector !== filters.sector) return false;
      if (filters.peMin && s.pe < Number(filters.peMin)) return false;
      if (filters.peMax && s.pe > Number(filters.peMax)) return false;
      if (filters.roeMin && s.roe < Number(filters.roeMin)) return false;
      if (filters.capFilter === 'Large' && s.marketCapB < 100) return false;
      if (filters.capFilter === 'Mega' && s.marketCapB < 500) return false;
      return true;
    });
  }, [apiStocks, stocks, filters]);

  const updateFilter = <K extends keyof ScreenerFilters>(key: K, value: ScreenerFilters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
          Equity Screener
        </h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          {filtered.length} results matching filters
        </p>
      </div>

      {/* Filter Bar */}
      <div className="terminal-panel" style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        flexWrap: 'wrap',
        marginBottom: 'var(--panel-gap)',
        padding: '8px 12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="terminal-label">Sector</span>
          <select style={selectStyle} value={filters.sector} onChange={(e) => updateFilter('sector', e.target.value)}>
            {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="terminal-label">Market Cap</span>
          <select style={selectStyle} value={filters.capFilter} onChange={(e) => updateFilter('capFilter', e.target.value)}>
            <option value="All">All</option>
            <option value="Mega">Mega (&gt;$500B)</option>
            <option value="Large">Large (&gt;$100B)</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="terminal-label">P/E</span>
          <input style={inputStyle} placeholder="Min" value={filters.peMin} onChange={(e) => updateFilter('peMin', e.target.value)} />
          <span style={{ color: 'var(--color-text-tertiary)' }}>&ndash;</span>
          <input style={inputStyle} placeholder="Max" value={filters.peMax} onChange={(e) => updateFilter('peMax', e.target.value)} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="terminal-label">ROE Min</span>
          <input style={inputStyle} placeholder="%" value={filters.roeMin} onChange={(e) => updateFilter('roeMin', e.target.value)} />
        </div>
      </div>

      {/* Results Table */}
      <div className="terminal-panel">
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} height="28px" />)}
          </div>
        ) : (
          <table className="terminal-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Sector</th>
                <th className="right">Market Cap</th>
                <th className="right">P/E</th>
                <th className="right">ROE</th>
                <th className="right">Rev Growth</th>
                <th className="right">Piotroski</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.ticker}>
                  <td style={{ fontWeight: 600, color: 'var(--color-accent-primary)' }}>{s.ticker}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>{s.name}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>{s.sector}</td>
                  <td className="right">{formatCap(s.marketCapB)}</td>
                  <td className="right">{s.pe.toFixed(1)}x</td>
                  <td className="right" style={{ color: signalColor(s.roe) }}>{s.roe.toFixed(1)}%</td>
                  <td className="right" style={{ color: signalColor(s.revGrowth) }}>
                    {s.revGrowth >= 0 ? '+' : ''}{s.revGrowth.toFixed(1)}%
                  </td>
                  <td className="right" style={{ color: qualityColor(s.piotroski), fontWeight: 600 }}>
                    {s.piotroski}/9
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
