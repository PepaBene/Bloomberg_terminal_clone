// ---------------------------------------------------------------------------
// Equity Screener Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo, useCallback } from 'react';
import { ScreenBuilder, ScreenResults, LivePreviewCount } from '@/components/screener';
import type { ScreenFilter, MetricDef, ScreenResultColumn } from '@/components/screener';
import { useScreenPrebuilt, useScreenHistory, useScreenFields, useRunScreen, useSaveScreen } from '@/hooks';

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

// --- ScreenBuilder fallback metrics ------------------------------------------

const FALLBACK_EQUITY_METRICS: MetricDef[] = [
  { key: 'pe_trailing', label: 'P/E Ratio', category: 'Valuation' },
  { key: 'ev_ebitda', label: 'EV/EBITDA', category: 'Valuation' },
  { key: 'market_cap', label: 'Market Cap ($B)', category: 'Size' },
  { key: 'roe', label: 'ROE (%)', category: 'Profitability' },
  { key: 'revenue_growth_1y', label: 'Revenue Growth (%)', category: 'Growth' },
  { key: 'piotroski_score', label: 'Piotroski F-Score', category: 'Quality' },
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

// --- Operator mapping for backend compatibility (Bug 46 fix) -----------------

function mapOperatorToBackend(op: string): string {
  switch (op) {
    case '>': return 'GT';
    case '<': return 'LT';
    case '>=': return 'GTE';
    case '<=': return 'LTE';
    case '=': return 'EQ';
    case '!=': return 'NEQ';
    case 'between': return 'BETWEEN';
    default: return op.toUpperCase();
  }
}

// --- Component ---------------------------------------------------------------

export default function ScreenerDashboard() {
  const [filters, setFilters] = useState<ScreenFilter[]>([]);
  const [backendResults, setBackendResults] = useState<Record<string, unknown>[] | null>(null);
  const [screening, setScreening] = useState(false);
  const [screenName, setScreenName] = useState('');
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showLoadModal, setShowLoadModal] = useState(false);
  const [isUsingMock, setIsUsingMock] = useState(false);

  // --- API hooks ---
  // [Bug 84 fix] — `GET /v2/analytics/screens/library` and `/screens/saved`
  // both return bare JSON arrays (`response_model=list[...]`), not a
  // `{screens: [...]}` wrapper. Normalize to an array regardless of whether
  // the hook data itself is the array or (defensively) a `.screens`-wrapped
  // shape, so this keeps working if the backend ever adds a wrapper.
  const { data: apiPrebuilt } = useScreenPrebuilt() as { data: any };
  const { data: apiHistory, refetch: refetchHistory } = useScreenHistory() as { data: any; refetch: () => void };
  const prebuiltScreens: any[] = useMemo(
    () => (Array.isArray(apiPrebuilt) ? apiPrebuilt : Array.isArray(apiPrebuilt?.screens) ? apiPrebuilt.screens : []),
    [apiPrebuilt],
  );
  const savedScreens: any[] = useMemo(
    () => (Array.isArray(apiHistory) ? apiHistory : Array.isArray(apiHistory?.screens) ? apiHistory.screens : []),
    [apiHistory],
  );

  // [Bug 49 fix] — Load fields dynamically from useScreenFields()
  const { data: apiFields } = useScreenFields() as { data: any };
  const availableMetrics: MetricDef[] = useMemo(() => {
    if (apiFields && Array.isArray((apiFields as any)?.fields)) {
      return (apiFields as any).fields.map((f: any) => ({
        key: f.name ?? f.key ?? f.field,
        label: f.label ?? f.display_name ?? f.name,
        category: f.category ?? 'Other',
      }));
    }
    return FALLBACK_EQUITY_METRICS;
  }, [apiFields]);

  const { mutateAsync: runScreen } = useRunScreen();
  const { mutateAsync: saveScreen } = useSaveScreen();

  // --- Run screen against backend (Bug 46 fix — correct filter format) ---
  const handleRunScreen = useCallback(async () => {
    if (filters.length === 0) { setBackendResults(null); setIsUsingMock(false); return; }
    setScreening(true);
    setIsUsingMock(false);
    try {
      // [Bug 46 fix] — Map filter fields to match backend ScreenFilter schema:
      // metric → field, operator → op (uppercase), valueTo → value2, add source.
      // The backend's `ScreenRequest` (src/schemas/screening.py:44) requires the
      // filter group to be wrapped under a `filters` key — i.e. the POST body is
      // `{filters: {logic, filters: [...]}}`, not a top-level `{logic, filters}`.
      const payload = {
        filters: {
          logic: 'AND',
          filters: filters.map(f => ({
            field: f.metric,
            source: 'ANALYTICS_RESULT',
            op: mapOperatorToBackend(f.operator),
            value: f.value,
            value2: f.valueTo ?? null,
          })),
        },
      };
      const res = await runScreen(payload);
      setBackendResults((res as any)?.results ?? (res as any)?.data ?? []);
    } catch {
      // [Bug 85 fix] — Track that we're in mock mode
      setBackendResults(null);
      setIsUsingMock(true);
    }
    setScreening(false);
  }, [filters, runScreen]);

  // --- Save screen ---
  const handleSaveScreen = useCallback(async () => {
    if (!screenName.trim()) return;
    try {
      await saveScreen({ name: screenName, filters });
      setShowSaveModal(false);
      setScreenName('');
      refetchHistory();
    } catch { /* ignore */ }
  }, [screenName, filters, saveScreen, refetchHistory]);

  // --- Load prebuilt screen ---
  const handleLoadPrebuilt = useCallback((screen: any) => {
    if (screen?.filters) {
      setFilters(screen.filters);
      setBackendResults(null);
      setIsUsingMock(false);
    }
    setShowLoadModal(false);
  }, []);

  // --- Load saved screen from history ---
  const handleLoadSaved = useCallback((screen: any) => {
    if (screen?.filters) {
      setFilters(screen.filters);
      setBackendResults(null);
      setIsUsingMock(false);
    }
    setShowLoadModal(false);
  }, []);

  // Derive filtered results from mock data based on ScreenBuilder filters (local fallback)
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
    setBackendResults(null); // reset backend results on filter change
    setIsUsingMock(false);
  }, []);

  // Use backend results if available, otherwise fall back to local filtering
  const resultRows = useMemo(
    () => backendResults ?? filtered.map((s) => ({ ...s } as unknown as Record<string, unknown>)),
    [backendResults, filtered],
  );

  // [Bug 85 fix] — Show null count in mock mode so LivePreviewCount can display fallback message
  const totalCount = backendResults ? backendResults.length : (isUsingMock ? null : MOCK_STOCKS.length);

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
            Equity Screener
          </h1>
          <p className="terminal-label" style={{ marginTop: '4px' }}>
            Build custom screens with flexible filters
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn-ghost" onClick={() => setShowLoadModal(true)}>
            Load Screen
          </button>
          <button className="btn-ghost" onClick={() => setShowSaveModal(true)} disabled={filters.length === 0}>
            Save Screen
          </button>
          <button className="btn-primary" onClick={handleRunScreen} disabled={screening || filters.length === 0}>
            {screening ? 'Screening…' : 'Run Screen'}
          </button>
        </div>
      </div>

      {/* ScreenBuilder — [Bug 49 fix] uses dynamic metrics from API */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <ScreenBuilder
          filters={filters}
          onChange={handleFiltersChange}
          availableMetrics={availableMetrics}
        />
      </div>

      {/* LivePreviewCount — [Bug 85 fix] shows demo mode when backend unreachable */}
      {isUsingMock ? (
        <div style={{ padding: '8px 12px', marginBottom: '8px', borderRadius: '4px', background: 'color-mix(in srgb, var(--color-signal-warning, #f0ad4e) 10%, transparent)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-warning, #f0ad4e)' }}>
          Demo mode — backend unavailable. Showing local mock results.
        </div>
      ) : (
        <LivePreviewCount count={resultRows.length} total={totalCount ?? resultRows.length} />
      )}

      {/* ScreenResults replaces inline results table */}
      <div style={{ marginTop: 'var(--panel-gap)' }}>
        <ScreenResults results={resultRows} columns={RESULT_COLUMNS} />
      </div>

      {/* Prebuilt Screens */}
      {prebuiltScreens.length > 0 && (
        <div className="terminal-card" style={{ marginTop: 'var(--panel-gap)', padding: '12px' }}>
          <h3 className="terminal-section-title" style={{ fontSize: 'var(--text-sm)', marginBottom: '8px' }}>Prebuilt Screens</h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {prebuiltScreens.map((s: any, i: number) => (
              <button key={i} className="btn-ghost" onClick={() => handleLoadPrebuilt(s)} style={{ fontSize: 'var(--text-xs)' }}>
                {s.name ?? `Screen ${i + 1}`}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Save Screen Modal */}
      {showSaveModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div className="terminal-card" style={{ padding: '24px', minWidth: '360px' }}>
            <h3 className="terminal-section-title" style={{ marginBottom: '12px' }}>Save Screen</h3>
            <input
              type="text"
              className="terminal-input"
              placeholder="Screen name"
              value={screenName}
              onChange={e => setScreenName(e.target.value)}
              style={{ width: '100%', marginBottom: '12px' }}
            />
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button className="btn-ghost" onClick={() => setShowSaveModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveScreen} disabled={!screenName.trim()}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Load Screen Modal */}
      {showLoadModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div className="terminal-card" style={{ padding: '24px', minWidth: '420px', maxHeight: '60vh', overflow: 'auto' }}>
            <h3 className="terminal-section-title" style={{ marginBottom: '12px' }}>Load Screen</h3>

            {prebuiltScreens.length > 0 && (
              <>
                <h4 className="terminal-label" style={{ marginBottom: '8px' }}>Prebuilt</h4>
                {prebuiltScreens.map((s: any, i: number) => (
                  <div key={`pre-${i}`} className="terminal-row" style={{ padding: '6px 8px', cursor: 'pointer', borderBottom: '1px solid var(--color-border)' }} onClick={() => handleLoadPrebuilt(s)}>
                    {s.name ?? `Prebuilt ${i + 1}`}
                  </div>
                ))}
              </>
            )}

            {savedScreens.length > 0 && (
              <>
                <h4 className="terminal-label" style={{ marginTop: '12px', marginBottom: '8px' }}>Saved</h4>
                {savedScreens.map((s: any, i: number) => (
                  <div key={`saved-${i}`} className="terminal-row" style={{ padding: '6px 8px', cursor: 'pointer', borderBottom: '1px solid var(--color-border)' }} onClick={() => handleLoadSaved(s)}>
                    {s.name ?? `Saved ${i + 1}`}
                  </div>
                ))}
              </>
            )}

            <div style={{ marginTop: '12px', textAlign: 'right' }}>
              <button className="btn-ghost" onClick={() => setShowLoadModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
