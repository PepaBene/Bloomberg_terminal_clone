// ---------------------------------------------------------------------------
// Equity Screener Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo, useCallback } from 'react';
import { ScreenBuilder, ScreenResults, LivePreviewCount } from '@/components/screener';
import type { ScreenFilter, MetricDef, ScreenResultColumn } from '@/components/screener';

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

// --- ScreenBuilder available metrics -----------------------------------------

const EQUITY_METRICS: MetricDef[] = [
  { key: 'pe', label: 'P/E Ratio', category: 'Valuation' },
  { key: 'evEbitda', label: 'EV/EBITDA', category: 'Valuation' },
  { key: 'marketCapB', label: 'Market Cap ($B)', category: 'Size' },
  { key: 'roe', label: 'ROE (%)', category: 'Profitability' },
  { key: 'revGrowth', label: 'Revenue Growth (%)', category: 'Growth' },
  { key: 'piotroski', label: 'Piotroski F-Score', category: 'Quality' },
];

// --- ScreenResults columns ---------------------------------------------------

const RESULT_COLUMNS: ScreenResultColumn[] = [
  { key: 'ticker', label: 'Ticker' },
  { key: 'name', label: 'Name' },
  { key: 'sector', label: 'Sector' },
  { key: 'marketCapB', label: 'Market Cap', format: 'currency' },
  { key: 'pe', label: 'P/E', format: 'number' },
  { key: 'roe', label: 'ROE %', format: 'percent' },
  { key: 'revGrowth', label: 'Rev Growth %', format: 'percent' },
  { key: 'piotroski', label: 'Piotroski', format: 'number' },
];

// --- Component ---------------------------------------------------------------

export default function ScreenerDashboard() {
  const [filters, setFilters] = useState<ScreenFilter[]>([]);

  // Derive filtered results from mock data based on ScreenBuilder filters
  const filtered = useMemo(() => {
    if (filters.length === 0) return MOCK_STOCKS;
    return MOCK_STOCKS.filter((stock) => {
      return filters.every((f) => {
        const val = (stock as unknown as Record<string, unknown>)[f.metric];
        if (typeof val !== 'number') return true;
        switch (f.operator) {
          case '>': return val > f.value;
          case '<': return val < f.value;
          case '=': return Math.abs(val - f.value) < 0.01;
          case 'between': return val >= f.value && val <= (f.valueTo ?? Infinity);
          default: return true;
        }
      });
    });
  }, [filters]);

  const handleFiltersChange = useCallback((newFilters: ScreenFilter[]) => {
    setFilters(newFilters);
  }, []);

  // Convert to generic records for ScreenResults
  const resultRows = useMemo(
    () => filtered.map((s) => ({ ...s } as unknown as Record<string, unknown>)),
    [filtered],
  );

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
          Equity Screener
        </h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          Build custom screens with flexible filters
        </p>
      </div>

      {/* ScreenBuilder replaces inline filter controls */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <ScreenBuilder
          filters={filters}
          onChange={handleFiltersChange}
          availableMetrics={EQUITY_METRICS}
        />
      </div>

      {/* LivePreviewCount between builder and results */}
      <LivePreviewCount count={filtered.length} total={MOCK_STOCKS.length} />

      {/* ScreenResults replaces inline results table */}
      <div style={{ marginTop: 'var(--panel-gap)' }}>
        <ScreenResults results={resultRows} columns={RESULT_COLUMNS} />
      </div>
    </div>
  );
}
