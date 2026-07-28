// ---------------------------------------------------------------------------
// Valuation Dashboard — DCF Inputs, Multiples, Peer Valuation
// ---------------------------------------------------------------------------
import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useDuPont, useMultiplesHistory, usePeerComparison, useDCFModel, useFootballField, useSavePeerGroup } from '@/hooks';
import { api } from '@/api/client';
import { ANALYTICS } from '@/api/endpoints';
import { RatioDashboard } from '@/components/company/RatioDashboard';
import type { DuPontData, MultiplesPoint } from '@/components/company/RatioDashboard';
import { MultiplesOverTime, PeerScatter, DCFPanel, SensitivityMatrix, FootballField } from '@/components/valuation';
import type { MultiplesDataPoint, PeerPoint, DCFAssumptions, DCFResult, FootballFieldMethodology } from '@/components/valuation';

// --- API response shapes (subset of backend schemas we actually read) -------
// Kept minimal/local rather than `any` so a future backend shape change is
// caught by the compiler instead of silently producing `undefined`s.

interface MultipleHistoryPointApi {
  calculation_date: string;
  value: number | null;
}

interface MultipleHistoryResponseApi {
  security_id?: string;
  multiple_type?: string;
  data_points?: MultipleHistoryPointApi[];
}

interface DCFResponseApi {
  sensitivity_grid?: {
    wacc_values?: number[];
    growth_values?: number[];
    implied_prices?: (number | null)[][];
  } | null;
}

interface FootballFieldResponseApi {
  current_price?: number | null;
  methodologies?: FootballFieldMethodology[];
  consensus_view?: string | null;
}

/** Maps the raw metric_name persisted by the multiples engine to the chart field it feeds. */
function multipleTypeToField(type: string | undefined): 'pe' | 'evEbitda' | 'pbv' | 'ps' | null {
  switch ((type ?? '').toLowerCase()) {
    case 'pe_trailing':
    case 'pe_forward':
      return 'pe';
    case 'ev_ebitda':
      return 'evEbitda';
    case 'pb':
    case 'p_tbv':
      return 'pbv';
    case 'ps':
      return 'ps';
    default:
      return null;
  }
}

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

// --- Empty/default fallback data --------------------------------------------
// We deliberately avoid hardcoded Apple/MSFT/GOOGL data here so the page
// shows a true empty state when the API hasn't returned data, instead of
// rendering Apple's valuation as if it belonged to whichever entity the
// user is viewing.

const EMPTY_PEER_VALUATION: { ticker: string; name: string; pe: number; evEbitda: number; pfcf: number; evRev: number; mktCap: string }[] = [];

const EMPTY_DUPONT: DuPontData = {
  roe: 0,
  profitMargin: 0,
  assetTurnover: 0,
  equityMultiplier: 0,
};

const EMPTY_MULTIPLES_HISTORY: MultiplesPoint[] = [];

const EMPTY_MULTIPLES_OVER_TIME: MultiplesDataPoint[] = [];

const EMPTY_PEER_SCATTER: PeerPoint[] = [];

const DEFAULT_DCF_ASSUMPTIONS: DCFAssumptions = {
  wacc: 0.10,
  terminalGrowth: 0.025,
  projectionYears: 10,
  currentFCF: 0,
};

const EMPTY_DCF_RESULT: DCFResult = {
  enterpriseValue: 0,
  equityValue: 0,
  impliedPrice: 0,
  currentPrice: 0,
  upside: 0,
};

// --- SensitivityMatrix axis defaults -----------------------------------------
// The axis tick values are reasonable defaults so the empty grid still
// renders with sensible labels; the price matrix is empty until real DCF
// sensitivity data lands.

const EMPTY_WACC_VALUES: number[] = [];
const EMPTY_GROWTH_VALUES: number[] = [];
const EMPTY_PRICE_MATRIX: number[][] = [];

// --- Component ---------------------------------------------------------------

export default function ValuationDashboard() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // [Bug 83 fix] — Read company info from store instead of hardcoding
  const companyName = primary?.name ?? primary?.ticker ?? 'Unknown';
  const companyTicker = primary?.ticker ?? resolvedId ?? '--';
  const companyPrice = (primary as any)?.price ?? (primary as any)?.last_price;

  // Wire hooks
  const { data: apiDupont } = useDuPont(resolvedId);
  const { data: apiMultiples } = useMultiplesHistory(resolvedId);
  const { data: apiPeers } = usePeerComparison(resolvedId);
  const { data: apiDcf } = useDCFModel(resolvedId);
  const { data: apiFootball } = useFootballField(resolvedId);

  // Use API data with mock fallback
  const activeDupont = (apiDupont as any) ?? EMPTY_DUPONT;
  const activeDcfAssumptions = (apiDcf as any)?.assumptions ?? DEFAULT_DCF_ASSUMPTIONS;
  const activeDcfResult = (apiDcf as any)?.result ?? EMPTY_DCF_RESULT;
  const hasDcfModel = Boolean((apiDcf as any)?.assumptions && (apiDcf as any)?.result);

  // [Bug 79 fix] — The real backend (`GET /v2/analytics/multiples/{id}/history`)
  // returns `{ multiple_type, data_points: [{calculation_date, value}] }`, not a
  // `.history` array of multi-metric points. Read `data_points`, map the single
  // metric it represents into the chart-friendly shape, and guard with
  // `Array.isArray` so an unexpected future shape degrades to an empty series
  // instead of throwing when passed into `.map()` downstream.
  const multiplesResp = apiMultiples as MultipleHistoryResponseApi | undefined;
  const multiplesDataPoints: MultipleHistoryPointApi[] = Array.isArray(multiplesResp?.data_points)
    ? multiplesResp!.data_points!
    : [];
  const multiplesField = multipleTypeToField(multiplesResp?.multiple_type);

  const activeMultiplesHistory: MultiplesPoint[] = useMemo(() => {
    if (multiplesDataPoints.length === 0) return EMPTY_MULTIPLES_HISTORY;
    return multiplesDataPoints.map((d) => ({
      period: d.calculation_date,
      pe: multiplesField === 'pe' ? (d.value ?? 0) : 0,
      evEbitda: multiplesField === 'evEbitda' ? (d.value ?? 0) : 0,
      pbv: multiplesField === 'pbv' ? (d.value ?? 0) : 0,
    }));
  }, [multiplesDataPoints, multiplesField]);

  const activeMultiplesOverTime: MultiplesDataPoint[] = useMemo(() => {
    if (multiplesDataPoints.length === 0) return EMPTY_MULTIPLES_OVER_TIME;
    return multiplesDataPoints.map((d) => ({
      date: d.calculation_date,
      pe: multiplesField === 'pe' ? (d.value ?? 0) : 0,
      evEbitda: multiplesField === 'evEbitda' ? (d.value ?? 0) : 0,
      ps: multiplesField === 'ps' ? (d.value ?? 0) : 0,
      pbv: multiplesField === 'pbv' ? (d.value ?? 0) : 0,
    }));
  }, [multiplesDataPoints, multiplesField]);

  // [Bug 82 fix] — The real backend (`GET /v2/analytics/ratios/{id}/vs-peers`)
  // returns `{ comparisons: [...] }` — per-metric percentile aggregates, NOT
  // an array of per-peer `{ticker,x,y,marketCap}` scatter points. No backend
  // endpoint currently exposes per-peer scatter points (checked `PeerGroupResponse`
  // at `/peers/{id}`, which only carries `{ticker, name, market_cap, similarity_score}`
  // — no per-peer P/E or revenue-growth values to plot). Rather than fabricate
  // fake peer points, guard strictly and show an empty/placeholder state until
  // a real per-peer-point endpoint exists (backend work, out of scope here).
  const activePeers: PeerPoint[] = Array.isArray(apiPeers) ? (apiPeers as PeerPoint[]) : EMPTY_PEER_SCATTER;

  // [Bug 81 fix] — `GET /v2/analytics/dcf/{id}/sensitivity` does not exist in
  // the backend at all; the main DCF response already carries `sensitivity_grid`
  // (`{wacc_values, growth_values, implied_prices}`) so read it from there
  // instead of calling the nonexistent endpoint.
  const _sens = (apiDcf as DCFResponseApi | undefined)?.sensitivity_grid;
  const activeWaccValues = _sens?.wacc_values ?? EMPTY_WACC_VALUES;
  const activeGrowthValues = _sens?.growth_values ?? EMPTY_GROWTH_VALUES;
  const activePriceMatrix = _sens?.implied_prices ?? EMPTY_PRICE_MATRIX;

  // [Bug 80 fix] — Wire football field data from API; a real `FootballField`
  // chart is rendered below (see JSX) instead of leaving this fetched-but-unused.
  const footballResp = apiFootball as FootballFieldResponseApi | undefined;
  const activeFootballMethodologies: FootballFieldMethodology[] = Array.isArray(footballResp?.methodologies)
    ? footballResp!.methodologies!
    : [];

  // Get current price from API data or store
  const currentPrice = (apiDcf as any)?.result?.currentPrice ?? companyPrice;

  // [Bug 82 fix] — Wire peer valuation table to API data
  const activePeerValuation = useMemo(() => {
    if (apiPeers && Array.isArray(apiPeers)) {
      return apiPeers;
    }
    return EMPTY_PEER_VALUATION;
  }, [apiPeers]);

  // Editable DCF inputs
  const [editableWacc, setEditableWacc] = useState<number>(activeDcfAssumptions.wacc);
  const [editableGrowth, setEditableGrowth] = useState<number>(activeDcfAssumptions.terminalGrowth);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lassoPeers, setLassoPeers] = useState<string[]>([]);
  const savePeers = useSavePeerGroup(resolvedId);
  const [dcfError, setDcfError] = useState<string | null>(null);

  // [Bug 78 fix] — Fixed DCF recalculate POST URL to use correct backend path
  const handleDCFRecalculate = useCallback(async () => {
    if (!resolvedId) return;
    setIsSubmitting(true);
    setDcfError(null);
    try {
      await api.post(ANALYTICS.dcfPost(resolvedId), {
        wacc: editableWacc,
        terminalGrowth: editableGrowth,
      });
    } catch (err) {
      // [Bug 78 fix] — Show error feedback instead of silently catching
      setDcfError(err instanceof Error ? err.message : 'DCF recalculation failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }, [resolvedId, editableWacc, editableGrowth]);

  const handleLassoSelect = useCallback((tickers: string[]) => {
    setLassoPeers(tickers);
    if (tickers.length > 0) {
      savePeers.mutate(tickers);
    }
  }, [savePeers]);

  const displayPeers = useMemo(() => {
    return lassoPeers.length > 0
      ? activePeerValuation.filter((p: any) => lassoPeers.includes(p.ticker) || p.ticker === companyTicker)
      : activePeerValuation;
  }, [lassoPeers, activePeerValuation, companyTicker]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Valuation Dashboard
        </h1>
        {/* [Bug 83 fix] — Dynamic company header from store */}
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {companyTicker} &mdash; {companyName}{companyPrice ? ` — $${Number(companyPrice).toFixed(2)}` : ''}
        </p>
      </div>

      {/* DuPont Decomposition + Multiples History via RatioDashboard */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        {apiDupont ? <RatioDashboard dupont={activeDupont} multiplesHistory={activeMultiplesHistory} /> : <p style={labelStyle}>DuPont analysis is unavailable for this entity.</p>}
      </div>

      {/* MultiplesOverTime (5Y history) — [Bug 79 fix] wired to API data */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Multiples Over Time (5Y)</h2>
        <MultiplesOverTime
          data={activeMultiplesOverTime}
          peerMedians={{ pe: 29.0, evEbitda: 19.2 }}
        />
      </div>

      {/* PeerScatter: P/E vs Revenue Growth — [Bug 82 fix] wired to API data */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Peer Comparison: P/E vs Revenue Growth</h2>
        <PeerScatter
          peers={activePeers}
          xLabel="Revenue Growth (%)"
          yLabel="P/E Ratio"
          highlightTicker={companyTicker}
          onLassoSelect={handleLassoSelect}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Editable DCF Inputs */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>DCF Model Inputs</h2>
          <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-end' }}>
            <div>
              <label style={labelStyle}>WACC (%)</label>
              <input
                type="number"
                step="0.001"
                value={(editableWacc * 100).toFixed(1)}
                onChange={(e) => setEditableWacc(parseFloat(e.target.value) / 100)}
                style={{
                  display: 'block', marginTop: '4px', width: '120px', padding: '6px 10px', borderRadius: '4px',
                  border: '1px solid var(--color-surface-border)', background: 'var(--color-surface-raised)',
                  color: 'var(--color-text-primary)', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)',
                }}
              />
            </div>
            <div>
              <label style={labelStyle}>Terminal Growth (%)</label>
              <input
                type="number"
                step="0.001"
                value={(editableGrowth * 100).toFixed(1)}
                onChange={(e) => setEditableGrowth(parseFloat(e.target.value) / 100)}
                style={{
                  display: 'block', marginTop: '4px', width: '120px', padding: '6px 10px', borderRadius: '4px',
                  border: '1px solid var(--color-surface-border)', background: 'var(--color-surface-raised)',
                  color: 'var(--color-text-primary)', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)',
                }}
              />
            </div>
            <button
              onClick={handleDCFRecalculate}
              disabled={isSubmitting}
              style={{
                padding: '6px 20px', borderRadius: '4px', border: 'none', cursor: isSubmitting ? 'wait' : 'pointer',
                background: 'var(--color-accent-primary)', color: '#fff',
                fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 500,
              }}
            >
              {isSubmitting ? 'Calculating...' : 'Recalculate'}
            </button>
          </div>
          {/* [Bug 78 fix] — Show DCF recalculate errors to user */}
          {dcfError && (
            <div style={{ marginTop: '8px', padding: '6px 10px', borderRadius: '4px', background: 'color-mix(in srgb, var(--color-signal-negative) 10%, transparent)', color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)' }}>
              {dcfError}
            </div>
          )}
        </div>

        {/* DCFPanel Component */}
        <div style={{ gridColumn: '1 / -1' }}>
          {hasDcfModel ? <DCFPanel assumptions={activeDcfAssumptions} result={activeDcfResult} onRecalculate={handleDCFRecalculate} /> : <div style={panelStyle}>No DCF model has been calculated for this entity.</div>}
        </div>

        {/* Football Field — [Bug 80 fix] the fetched-but-never-rendered football
            field data now feeds a real chart instead of being dead code. */}
        <div style={{ gridColumn: '1 / -1' }}>
          <FootballField
            methodologies={activeFootballMethodologies}
            currentPrice={footballResp?.current_price ?? currentPrice}
            consensusView={footballResp?.consensus_view}
          />
        </div>

        {/* SensitivityMatrix — [Bug 81 fix] wired to API data */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>WACC / Terminal Growth Sensitivity ($)</h2>
          {activeWaccValues.length && activeGrowthValues.length && activePriceMatrix.length ? <SensitivityMatrix waccValues={activeWaccValues} growthValues={activeGrowthValues} priceMatrix={activePriceMatrix} currentPrice={currentPrice} /> : <p style={labelStyle}>No DCF sensitivity grid is available.</p>}
        </div>

        {/* Peer Valuation Table — [Bug 82 fix] wired to API data */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Peer Valuation</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Ticker', 'P/E', 'EV/EBITDA', 'P/FCF', 'EV/Rev', 'Mkt Cap'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Ticker' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayPeers.map((p: any) => (
                <tr key={p.ticker} style={{ height: 'var(--table-row-height)', background: p.ticker === companyTicker ? 'var(--color-surface-overlay)' : 'transparent' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{p.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{typeof p.pe === 'number' ? `${p.pe.toFixed(1)}x` : '--'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{typeof p.evEbitda === 'number' ? `${p.evEbitda.toFixed(1)}x` : '--'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{typeof p.pfcf === 'number' ? `${p.pfcf.toFixed(1)}x` : '--'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{typeof p.evRev === 'number' ? `${p.evRev.toFixed(1)}x` : '--'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${p.mktCap}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
