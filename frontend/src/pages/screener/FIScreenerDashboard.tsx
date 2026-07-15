// ---------------------------------------------------------------------------
// Fixed Income Screener Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo, useCallback } from 'react';
import { ScreenBuilder, ScreenResults, LivePreviewCount } from '@/components/screener';
import type { ScreenFilter, MetricDef, ScreenResultColumn } from '@/components/screener';
import { EmptyState } from '@/components/feedback';
import { api } from '@/api/client';

// Real backend route: POST /v2/analytics/bonds/screen (src/api/routers/
// fi_screening.py — router self-prefixes /v2/analytics). The FI.screen
// constant in endpoints.ts points at the legacy /v1/fi/screen/bonds path
// that 404s, so the correct path is inlined here.
const BOND_SCREEN_PATH = '/v2/analytics/bonds/screen';

// --- DTOs mirroring the backend Pydantic schemas (src/schemas/fi_screening.py)

interface BondScreenFilterInput {
  field: string;
  op: string; // GT, LT, EQ, BETWEEN
  value: number;
  value2?: number;
}

interface BondScreenRequest {
  filters: BondScreenFilterInput[];
  sort_by?: string;
  ascending?: boolean;
  limit?: number;
}

interface BondScreenResult {
  cusip: string;
  name: string | null;
  coupon_rate: number | null;
  maturity_date: string | null;
  spread_bps: number | null;
  yield_to_worst: number | null;
  liquidity_score: number | null;
  is_investment_grade: boolean | null;
}

interface BondScreenResponse {
  results: BondScreenResult[];
  total: number;
}

// Map the ScreenBuilder operator vocabulary to the backend op codes.
const OP_MAP: Record<ScreenFilter['operator'], string> = {
  '>': 'GT',
  '<': 'LT',
  '=': 'EQ',
  between: 'BETWEEN',
};

// --- Bond-specific ScreenBuilder metrics -------------------------------------
// Keys are the real backend filterable fields (see the bond_dict built in
// fi_screening.py's screen_bonds), so a ScreenFilter maps 1:1 to a backend
// filter. Duration/price are dropped — the backend exposes no such field.

const BOND_METRICS: MetricDef[] = [
  { key: 'spread_bps', label: 'G-Spread (bps)', category: 'Spread' },
  { key: 'yield_to_worst', label: 'Yield to Worst (%)', category: 'Yield' },
  { key: 'coupon_rate', label: 'Coupon (%)', category: 'Income' },
  { key: 'liquidity_score', label: 'Liquidity Score', category: 'Liquidity' },
];

// --- ScreenResults columns ---------------------------------------------------
// Only fields present on BondScreenResult. `grade` is derived from the real
// is_investment_grade boolean below.

const BOND_COLUMNS: ScreenResultColumn[] = [
  { key: 'cusip', label: 'CUSIP' },
  { key: 'name', label: 'Issuer' },
  { key: 'grade', label: 'Grade' },
  { key: 'coupon_rate', label: 'Coupon', format: 'percent' },
  { key: 'maturity_date', label: 'Maturity' },
  { key: 'spread_bps', label: 'G-Spread (bps)', format: 'number' },
  { key: 'yield_to_worst', label: 'YTW', format: 'percent' },
  { key: 'liquidity_score', label: 'Liquidity', format: 'number' },
];

// --- Component ---------------------------------------------------------------

export default function FIScreenerDashboard() {
  const [filters, setFilters] = useState<ScreenFilter[]>([]);
  const [results, setResults] = useState<BondScreenResult[] | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'done'>('idle');

  const handleRunScreen = useCallback(async () => {
    setStatus('loading');
    try {
      const body: BondScreenRequest = {
        filters: filters.map((f) => ({
          field: f.metric,
          op: OP_MAP[f.operator],
          value: f.value,
          value2: f.operator === 'between' ? f.valueTo : undefined,
        })),
        sort_by: 'spread_bps',
        ascending: false,
        limit: 50,
      };
      const response = await api.post<BondScreenResponse>(BOND_SCREEN_PATH, body);
      setResults(response.results ?? []);
      setStatus('done');
    } catch {
      setResults(null);
      setStatus('error');
    }
  }, [filters]);

  const handleFiltersChange = useCallback((newFilters: ScreenFilter[]) => {
    setFilters(newFilters);
  }, []);

  const resultRows = useMemo(
    () =>
      (results ?? []).map((b) => ({
        ...b,
        grade: b.is_investment_grade == null ? '—' : b.is_investment_grade ? 'IG' : 'HY',
      })) as Record<string, unknown>[],
    [results],
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Screener
        </h1>
        <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
          Screen corporate bonds by G-Spread, Yield to Worst, Coupon, and Liquidity
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
          disabled={status === 'loading'}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            padding: '8px 20px',
            background: 'var(--color-accent)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: status === 'loading' ? 'default' : 'pointer',
            opacity: status === 'loading' ? 0.6 : 1,
          }}
        >
          {status === 'loading' ? 'Running…' : 'Run Screen'}
        </button>
      </div>

      {/* LivePreviewCount between builder and results */}
      <LivePreviewCount count={results ? results.length : null} loading={status === 'loading'} />

      {/* Results */}
      <div style={{ marginTop: 'var(--panel-gap)' }}>
        {status === 'idle' && (
          <EmptyState icon="🔎" title="Run a screen to see results" description="Add filters above (optional) and click Run Screen to query the bond universe." />
        )}
        {status === 'error' && (
          <EmptyState icon="⚠️" title="Screen failed" description="The bond screening request could not be completed. Please try again." action={{ label: 'Retry', onClick: handleRunScreen }} />
        )}
        {status === 'done' && resultRows.length === 0 && (
          <EmptyState icon="📭" title="No bonds matched" description="No bonds matched the current filters. Try relaxing your criteria." />
        )}
        {status === 'done' && resultRows.length > 0 && (
          <ScreenResults results={resultRows} columns={BOND_COLUMNS} />
        )}
      </div>
    </div>
  );
}
