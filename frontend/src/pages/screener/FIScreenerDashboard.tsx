// ---------------------------------------------------------------------------
// Fixed Income Screener Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo, useCallback } from 'react';
import { ScreenBuilder, ScreenResults, LivePreviewCount } from '@/components/screener';
import type { ScreenFilter, MetricDef, ScreenResultColumn } from '@/components/screener';
import { api } from '@/api/client';

// --- Mock Data ---------------------------------------------------------------

interface BondRow {
  cusip: string;
  issuer: string;
  coupon: number;
  maturity: string;
  rating: string;
  ratingCategory: 'IG' | 'HY';
  sector: string;
  maturityBucket: string;
  oas: number;
  ytm: number;
  price: number;
  duration: number;
}

const mockBonds: BondRow[] = [
  { cusip: '037833100', issuer: 'Apple Inc.',        coupon: 4.125, maturity: '2028-05-15', rating: 'AA+', ratingCategory: 'IG', sector: 'Technology', maturityBucket: '3-5Y', oas: 52,  ytm: 4.68,  price: 98.42, duration: 2.8 },
  { cusip: '594918104', issuer: 'Microsoft Corp.',   coupon: 3.750, maturity: '2027-08-08', rating: 'AAA', ratingCategory: 'IG', sector: 'Technology', maturityBucket: '1-3Y', oas: 38,  ytm: 4.32,  price: 99.18, duration: 1.4 },
  { cusip: '46625H100', issuer: 'JPMorgan Chase',    coupon: 5.250, maturity: '2033-01-15', rating: 'A+',  ratingCategory: 'IG', sector: 'Financials', maturityBucket: '5-10Y', oas: 95,  ytm: 5.42,  price: 101.24, duration: 6.2 },
  { cusip: '38141G104', issuer: 'Goldman Sachs',     coupon: 5.750, maturity: '2034-10-01', rating: 'A',   ratingCategory: 'IG', sector: 'Financials', maturityBucket: '5-10Y', oas: 118, ytm: 5.88,  price: 99.86, duration: 7.1 },
  { cusip: '172967424', issuer: 'Citigroup Inc.',    coupon: 6.125, maturity: '2036-07-15', rating: 'BBB+', ratingCategory: 'IG', sector: 'Financials', maturityBucket: '10+Y', oas: 142, ytm: 6.18,  price: 97.62, duration: 8.4 },
  { cusip: '345370860', issuer: 'Ford Motor Co.',    coupon: 6.625, maturity: '2028-02-15', rating: 'BB+', ratingCategory: 'HY', sector: 'Consumer Disc.', maturityBucket: '1-3Y', oas: 225, ytm: 6.84,  price: 100.52, duration: 1.8 },
  { cusip: '120568AE5', issuer: 'T-Mobile US',      coupon: 5.375, maturity: '2031-04-15', rating: 'BBB', ratingCategory: 'IG', sector: 'Telecom',    maturityBucket: '5-10Y', oas: 108, ytm: 5.52,  price: 98.94, duration: 4.8 },
  { cusip: '26884LAC8', issuer: 'Energy Transfer',   coupon: 7.125, maturity: '2029-08-01', rating: 'BB',  ratingCategory: 'HY', sector: 'Energy',     maturityBucket: '3-5Y', oas: 268, ytm: 7.34,  price: 99.28, duration: 3.2 },
];

// --- Bond-specific ScreenBuilder metrics -------------------------------------

const BOND_METRICS: MetricDef[] = [
  { key: 'oas', label: 'OAS (bps)', category: 'Spread' },
  { key: 'ytm', label: 'Yield to Maturity (%)', category: 'Yield' },
  { key: 'duration', label: 'Duration (yrs)', category: 'Risk' },
  { key: 'coupon', label: 'Coupon (%)', category: 'Income' },
  { key: 'price', label: 'Price', category: 'Pricing' },
];

// --- ScreenResults columns ---------------------------------------------------

const BOND_COLUMNS: ScreenResultColumn[] = [
  { key: 'cusip', label: 'CUSIP' },
  { key: 'issuer', label: 'Issuer' },
  { key: 'rating', label: 'Rating' },
  { key: 'coupon', label: 'Coupon', format: 'percent' },
  { key: 'maturity', label: 'Maturity' },
  { key: 'oas', label: 'OAS (bps)', format: 'number' },
  { key: 'duration', label: 'Duration', format: 'number' },
  { key: 'ytm', label: 'YTM', format: 'percent' },
  { key: 'price', label: 'Price', format: 'number' },
];

// --- Component ---------------------------------------------------------------

export default function FIScreenerDashboard() {
  const [filters, setFilters] = useState<ScreenFilter[]>([]);
  const [backendResults, setBackendResults] = useState<BondRow[] | null>(null);

  const handleRunScreen = useCallback(async () => {
    try {
      const result = await api.post('/v1/fi/screen/bonds', { filters });
      setBackendResults((result as any)?.results ?? null);
    } catch { setBackendResults(null); }
  }, [filters]);

  const filtered = useMemo(() => {
    if (filters.length === 0) return mockBonds;
    return mockBonds.filter((bond) => {
      return filters.every((f) => {
        const val = (bond as unknown as Record<string, unknown>)[f.metric];
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

  const displayData = backendResults ?? filtered;

  const resultRows = useMemo(
    () => displayData.map((b) => ({ ...b } as Record<string, unknown>)),
    [displayData],
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Screener
        </h1>
        <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
          Screen bonds by Rating, OAS, Duration, Coupon, and Maturity
        </p>
      </div>

      {/* ScreenBuilder replaces inline filter controls */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <ScreenBuilder
          filters={filters}
          onChange={handleFiltersChange}
          availableMetrics={BOND_METRICS}
        />
      </div>

      {/* Run Screen button */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <button
          onClick={handleRunScreen}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            padding: '8px 20px',
            background: 'var(--color-accent)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Run Screen
        </button>
      </div>

      {/* LivePreviewCount between builder and results */}
      <LivePreviewCount count={displayData.length} total={mockBonds.length} />

      {/* ScreenResults replaces inline results table */}
      <div style={{ marginTop: 'var(--panel-gap)' }}>
        <ScreenResults results={resultRows} columns={BOND_COLUMNS} />
      </div>
    </div>
  );
}
