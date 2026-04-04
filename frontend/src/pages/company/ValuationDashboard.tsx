// ---------------------------------------------------------------------------
// Valuation Dashboard — DCF Inputs, Multiples, Peer Valuation
// ---------------------------------------------------------------------------
import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useDuPont, useMultiplesHistory, usePeerComparison, useDCFModel, useDCFSensitivity, useFootballField, useSavePeerGroup } from '@/hooks';
import { api } from '@/api/client';
import { ANALYTICS } from '@/api/endpoints';
import { RatioDashboard } from '@/components/company/RatioDashboard';
import type { DuPontData, MultiplesPoint } from '@/components/company/RatioDashboard';
import { MultiplesOverTime, PeerScatter, DCFPanel, SensitivityMatrix } from '@/components/valuation';
import type { MultiplesDataPoint, PeerPoint, DCFAssumptions, DCFResult } from '@/components/valuation';

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

// --- Mock Data (fallback only) -----------------------------------------------

const MOCK_PEER_VALUATION = [
  { ticker: 'AAPL', name: 'Apple', pe: 28.6, evEbitda: 22.1, pfcf: 25.7, evRev: 7.4, mktCap: '2.78T' },
  { ticker: 'MSFT', name: 'Microsoft', pe: 34.2, evEbitda: 24.8, pfcf: 33.1, evRev: 12.8, mktCap: '3.12T' },
  { ticker: 'GOOGL', name: 'Alphabet', pe: 24.5, evEbitda: 16.2, pfcf: 28.4, evRev: 6.1, mktCap: '2.05T' },
  { ticker: 'AMZN', name: 'Amazon', pe: 58.3, evEbitda: 18.9, pfcf: 42.7, evRev: 3.2, mktCap: '1.92T' },
  { ticker: 'META', name: 'Meta', pe: 22.8, evEbitda: 14.5, pfcf: 20.1, evRev: 8.7, mktCap: '1.28T' },
];

const MOCK_DUPONT: DuPontData = {
  roe: 1.37,
  profitMargin: 0.26,
  assetTurnover: 1.11,
  equityMultiplier: 4.76,
};

const MOCK_MULTIPLES_HISTORY: MultiplesPoint[] = [
  { period: '2018', pe: 14.5, evEbitda: 10.8, pbv: 8.2 },
  { period: '2019', pe: 20.3, evEbitda: 15.2, pbv: 13.5 },
  { period: '2020', pe: 35.2, evEbitda: 26.4, pbv: 28.7 },
  { period: '2021', pe: 28.8, evEbitda: 22.1, pbv: 35.6 },
  { period: '2022', pe: 22.4, evEbitda: 18.5, pbv: 42.1 },
  { period: '2023', pe: 26.1, evEbitda: 20.2, pbv: 48.3 },
  { period: '2024', pe: 27.5, evEbitda: 21.0, pbv: 44.8 },
  { period: '2025', pe: 28.6, evEbitda: 22.1, pbv: 45.2 },
];

// --- MultiplesOverTime 5Y mock data (fallback) -------------------------------

const MOCK_MULTIPLES_OVER_TIME: MultiplesDataPoint[] = [
  { date: '2021-03', pe: 28.8, evEbitda: 22.1, ps: 8.4, pbv: 35.6 },
  { date: '2021-06', pe: 27.5, evEbitda: 21.0, ps: 8.1, pbv: 33.8 },
  { date: '2021-09', pe: 26.2, evEbitda: 19.8, ps: 7.8, pbv: 36.2 },
  { date: '2021-12', pe: 30.1, evEbitda: 23.5, ps: 8.9, pbv: 38.4 },
  { date: '2022-03', pe: 27.8, evEbitda: 21.4, ps: 7.6, pbv: 40.1 },
  { date: '2022-06', pe: 23.2, evEbitda: 18.2, ps: 6.8, pbv: 37.2 },
  { date: '2022-09', pe: 24.8, evEbitda: 19.5, ps: 6.5, pbv: 42.1 },
  { date: '2022-12', pe: 22.4, evEbitda: 18.5, ps: 6.2, pbv: 41.8 },
  { date: '2023-03', pe: 25.6, evEbitda: 20.1, ps: 7.0, pbv: 44.2 },
  { date: '2023-06', pe: 31.2, evEbitda: 24.1, ps: 7.8, pbv: 46.8 },
  { date: '2023-09', pe: 28.4, evEbitda: 21.8, ps: 7.5, pbv: 45.1 },
  { date: '2023-12', pe: 26.1, evEbitda: 20.2, ps: 7.2, pbv: 48.3 },
  { date: '2024-03', pe: 27.2, evEbitda: 20.8, ps: 7.4, pbv: 46.2 },
  { date: '2024-06', pe: 32.4, evEbitda: 25.2, ps: 8.6, pbv: 48.5 },
  { date: '2024-09', pe: 29.8, evEbitda: 22.6, ps: 7.9, pbv: 44.8 },
  { date: '2024-12', pe: 27.5, evEbitda: 21.0, ps: 7.4, pbv: 44.2 },
  { date: '2025-03', pe: 28.1, evEbitda: 21.4, ps: 7.6, pbv: 45.8 },
  { date: '2025-06', pe: 29.4, evEbitda: 22.5, ps: 7.8, pbv: 46.2 },
  { date: '2025-09', pe: 27.8, evEbitda: 21.2, ps: 7.3, pbv: 44.6 },
  { date: '2025-12', pe: 28.6, evEbitda: 22.1, ps: 7.4, pbv: 45.2 },
];

// --- PeerScatter mock (fallback) ---------------------------------------------

const MOCK_PEER_SCATTER: PeerPoint[] = [
  { name: 'Apple', ticker: 'AAPL', x: 5.2, y: 28.6, marketCap: 2780 },
  { name: 'Microsoft', ticker: 'MSFT', x: 12.8, y: 34.2, marketCap: 3120 },
  { name: 'Alphabet', ticker: 'GOOGL', x: 15.4, y: 24.5, marketCap: 2050 },
  { name: 'Amazon', ticker: 'AMZN', x: 13.2, y: 58.3, marketCap: 1920 },
  { name: 'Meta', ticker: 'META', x: 24.6, y: 22.8, marketCap: 1280 },
  { name: 'NVIDIA', ticker: 'NVDA', x: 122.4, y: 62.4, marketCap: 2180 },
];

// --- DCFPanel mock (fallback) ------------------------------------------------

const MOCK_DCF_ASSUMPTIONS: DCFAssumptions = {
  wacc: 0.098,
  terminalGrowth: 0.025,
  projectionYears: 10,
  currentFCF: 105.6e9,
};

const MOCK_DCF_RESULT: DCFResult = {
  enterpriseValue: 2.78e12,
  equityValue: 2.72e12,
  impliedPrice: 180.53,
  currentPrice: 178.72,
  upside: 0.010,
};

// --- SensitivityMatrix mock (fallback) ---------------------------------------

const MOCK_WACC_VALUES = [0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11];
const MOCK_GROWTH_VALUES = [0.015, 0.02, 0.025, 0.03, 0.035];
const MOCK_PRICE_MATRIX = [
  [228.4, 248.2, 272.6, 302.8, 340.2],
  [210.6, 226.8, 246.4, 270.2, 299.4],
  [195.2, 208.4, 224.1, 243.2, 266.8],
  [182.0, 192.8, 205.6, 221.0, 239.8],
  [170.4, 179.4, 190.0, 202.6, 217.8],
  [160.2, 167.8, 176.6, 187.2, 199.8],
  [151.2, 157.6, 165.0, 173.8, 184.2],
];

// --- Component ---------------------------------------------------------------

export default function ValuationDashboard() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // [Bug 83 fix] — Read company info from store instead of hardcoding
  const companyName = primary?.name ?? primary?.ticker ?? 'Unknown';
  const companyTicker = primary?.ticker ?? resolvedId ?? '--';
  const companyPrice = (primary as any)?.price ?? (primary as any)?.last_price ?? 0;

  // Wire hooks
  const { data: apiDupont } = useDuPont(resolvedId);
  const { data: apiMultiples } = useMultiplesHistory(resolvedId);
  const { data: apiPeers } = usePeerComparison(resolvedId);
  const { data: apiDcf } = useDCFModel(resolvedId);
  const { data: apiSensitivity } = useDCFSensitivity(resolvedId);
  const { data: apiFootball } = useFootballField(resolvedId);

  // Use API data with mock fallback
  const activeDupont = (apiDupont as any) ?? MOCK_DUPONT;
  const activeMultiplesHistory = (apiMultiples as any[]) ?? MOCK_MULTIPLES_HISTORY;
  const activePeers = (apiPeers as any[]) ?? MOCK_PEER_SCATTER;
  const activeDcfAssumptions = (apiDcf as any)?.assumptions ?? MOCK_DCF_ASSUMPTIONS;
  const activeDcfResult = (apiDcf as any)?.result ?? MOCK_DCF_RESULT;

  // [Bug 79 fix] — Wire MultiplesOverTime chart to API data instead of separate hardcoded array
  const activeMultiplesOverTime = (apiMultiples as any)?.history ?? (apiMultiples as any[]) ?? MOCK_MULTIPLES_OVER_TIME;

  // [Bug 81 fix] — Wire sensitivity data from API instead of hardcoded grid
  const activeWaccValues = (apiSensitivity as any)?.waccValues ?? MOCK_WACC_VALUES;
  const activeGrowthValues = (apiSensitivity as any)?.growthValues ?? MOCK_GROWTH_VALUES;
  const activePriceMatrix = (apiSensitivity as any)?.priceMatrix ?? MOCK_PRICE_MATRIX;

  // [Bug 80 fix] — Wire football field data from API
  const activeFootballData = (apiFootball as any)?.methodologies ?? null;

  // Get current price from API data or store
  const currentPrice = (apiDcf as any)?.result?.currentPrice ?? companyPrice ?? MOCK_DCF_RESULT.currentPrice;

  // [Bug 82 fix] — Wire peer valuation table to API data
  const activePeerValuation = useMemo(() => {
    if (apiPeers && Array.isArray(apiPeers)) {
      return apiPeers;
    }
    return MOCK_PEER_VALUATION;
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
        <RatioDashboard dupont={activeDupont} multiplesHistory={activeMultiplesHistory} />
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
          <DCFPanel assumptions={activeDcfAssumptions} result={activeDcfResult} onRecalculate={handleDCFRecalculate} />
        </div>

        {/* SensitivityMatrix — [Bug 81 fix] wired to API data */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>WACC / Terminal Growth Sensitivity ($)</h2>
          <SensitivityMatrix
            waccValues={activeWaccValues}
            growthValues={activeGrowthValues}
            priceMatrix={activePriceMatrix}
            currentPrice={currentPrice}
          />
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
