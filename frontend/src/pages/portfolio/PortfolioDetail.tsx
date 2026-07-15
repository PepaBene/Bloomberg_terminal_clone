// ---------------------------------------------------------------------------
// Portfolio Detail — Single Portfolio View
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { DonutChart, TimeSeriesChart } from '@/components/charts';
import {
  usePortfolio,
  usePortfolioPositions,
  usePortfolioNav,
  usePortfolioNavHistory,
  usePortfolioAllocationsBySector,
  usePortfolioPerformance,
} from '@/hooks';
import { api } from '@/api/client';
import { useToastStore } from '@/stores/toastStore';
import { ReportExportModal } from '@/components/ReportExportModal';

// --- Real API response shapes (src/schemas/portfolio.py, position.py,
// nav.py, performance.py) -- replaces `as any` casts (P4-F-022) with types
// matching what the backend actually returns. ---------------------------

interface ApiPortfolio {
  id: string;
  portfolio_name: string;
  inception_date: string;
  current_cash: number;
  status: string;
}

interface ApiPosition {
  id: string;
  ticker: string;
  shares: number | null;
  market_value: number | null;
  weight: number | null; // fraction, e.g. 0.032 for 3.2%
  day_change_pct: number | null; // already percent, e.g. 1.25 for +1.25%
  unrealized_pnl: number | null;
  closing_price: number | null;
}

interface ApiNav {
  nav: number;
}

interface ApiNavHistoryEntry {
  date: string;
  nav: number;
  daily_return: number | null; // fraction
  cumulative_return: number | null;
}

interface ApiNavHistoryResponse {
  history: ApiNavHistoryEntry[];
}

interface ApiSectorAllocation {
  name: string;
  value: number;
}

// PerformanceResponse (src/schemas/performance.py) -- returns/drawdown are
// fractions (e.g. 0.0842 for +8.42%), matching the same convention as
// src/engines/backtester.py::compute_performance_metrics.
interface ApiPerformance {
  twr_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  beta: number | null;
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

function NavHistoryChart({ data }: { data?: { date: string; value: number }[] }) {
  // P4-F-013: render an empty chart when the API hasn't returned NAV
  // history. The previous Math.random() walk made stale or missing data
  // look like real performance.
  return (
    <TimeSeriesChart
      data={data ?? []}
      height={200}
      showGrid
      series={[{ key: 'value', color: '#3B82F6', name: 'NAV', type: 'area' }]}
      yAxisFormat={(v: number) => `$${(v / 1_000_000).toFixed(2)}M`}
    />
  );
}

// --- Component ---------------------------------------------------------------

export default function PortfolioDetail() {
  const { portfolioId } = useParams<{ portfolioId: string }>();

  // API hooks — data falls back to mock constants via ?? below
  const { data: apiPortfolio } = usePortfolio(portfolioId) as { data: ApiPortfolio | undefined };
  const { data: apiPositions } = usePortfolioPositions(portfolioId) as { data: ApiPosition[] | undefined };
  const { data: apiNav } = usePortfolioNav(portfolioId) as { data: ApiNav | undefined };
  const { data: apiNavHistory } = usePortfolioNavHistory(portfolioId) as { data: ApiNavHistoryResponse | undefined };
  // [P4-F-013 note] No /v4/portfolios/{id}/allocations/sector route exists
  // anywhere in src/api/routers/ (verified by grep) -- a missing feature,
  // not a wiring bug, despite this hook having genuinely been wired up.
  // Falls back to mock until that endpoint exists.
  const { data: apiAllocations } = usePortfolioAllocationsBySector(portfolioId) as { data: ApiSectorAllocation[] | undefined };
  const { data: apiPerformance } = usePortfolioPerformance(portfolioId) as { data: ApiPerformance | null | undefined };

  const latestNavEntry = apiNavHistory?.history?.[apiNavHistory.history.length - 1];

  // Fallback: prefer API data, fall back to hardcoded mock data
  const activePortfolio = apiPortfolio
    ? {
        name: apiPortfolio.portfolio_name,
        nav: apiNav?.nav ?? portfolio.nav,
        dayChange: latestNavEntry?.daily_return != null ? latestNavEntry.daily_return * 100 : portfolio.dayChange,
        dayChangeDollar:
          latestNavEntry?.daily_return != null && apiNav?.nav != null
            ? apiNav.nav * latestNavEntry.daily_return
            : portfolio.dayChangeDollar,
        inception: apiPortfolio.inception_date,
      }
    : portfolio;
  const activeHoldings: Holding[] = Array.isArray(apiPositions)
    ? apiPositions.map((p) => ({
        ticker: p.ticker,
        // PositionResponse has no company-name field, only `ticker`.
        name: p.ticker,
        shares: p.shares ?? 0,
        price: p.closing_price ?? 0,
        marketValue: p.market_value ?? 0,
        weight: (p.weight ?? 0) * 100,
        dayChange: p.day_change_pct ?? 0,
        unrealizedPnl: p.unrealized_pnl ?? 0,
      }))
    : holdings;
  const activeAllocations: ApiSectorAllocation[] = Array.isArray(apiAllocations) ? apiAllocations : SECTOR_ALLOCATION;

  // [P4-F-013 fix] These 4 KPIs were rendered from the hardcoded
  // `perfMetrics` constant with zero hook consumption. Wired to the real
  // GET /v4/portfolios/{id}/performance endpoint, same ?? merge pattern
  // used by the rest of this page.
  const activePerfMetrics: PerformanceMetric[] = apiPerformance
    ? [
        { label: 'TWR (YTD)', value: apiPerformance.twr_return != null ? formatPct(apiPerformance.twr_return * 100) : '—' },
        { label: 'Sharpe Ratio', value: apiPerformance.sharpe_ratio != null ? apiPerformance.sharpe_ratio.toFixed(2) : '—' },
        { label: 'Max Drawdown', value: apiPerformance.max_drawdown != null ? formatPct(-Math.abs(apiPerformance.max_drawdown) * 100) : '—' },
        { label: 'Beta (vs SPX)', value: apiPerformance.beta != null ? apiPerformance.beta.toFixed(2) : '—' },
      ]
    : perfMetrics;

  // --- Export modal state ---
  const [showExport, setShowExport] = useState(false);

  // --- Add Position modal state ---
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [positionTicker, setPositionTicker] = useState('');
  const [positionShares, setPositionShares] = useState('');
  const [positionPrice, setPositionPrice] = useState('');
  const [positionSubmitting, setPositionSubmitting] = useState(false);

  const handleAddPosition = useCallback(async () => {
    if (!portfolioId || !positionTicker || !positionShares || !positionPrice) return;
    setPositionSubmitting(true);
    try {
      await api.post(`/v4/portfolios/${portfolioId}/positions`, {
        ticker: positionTicker,
        shares: Number(positionShares),
        price: Number(positionPrice),
      });
      setShowAddPosition(false);
      setPositionTicker('');
      setPositionShares('');
      setPositionPrice('');
    } catch (e) {
      console.error('Failed to add position', e);
      useToastStore.getState().showToast('Failed to add position. Please try again.');
    } finally {
      setPositionSubmitting(false);
    }
  }, [portfolioId, positionTicker, positionShares, positionPrice]);

  // --- What-If Analysis state ---
  const [whatIfScenario, setWhatIfScenario] = useState('market_drop_10');
  const [whatIfResults, setWhatIfResults] = useState<{ projectedNavChange?: number; projectedPnl?: number } | null>(null);
  const [whatIfRunning, setWhatIfRunning] = useState(false);

  const handleRunScenario = useCallback(async () => {
    if (!portfolioId) return;
    setWhatIfRunning(true);
    setWhatIfResults(null);
    try {
      // NOTE: no /v4/portfolios/{id}/what-if route exists anywhere in
      // src/api/routers/ (verified by grep) -- this always errors today.
      // `api.post` already returns the parsed JSON body directly (see
      // src/api/client.ts), not an axios-style `{ data }` wrapper, so the
      // previous `res.data as any` would have been wrong even if the
      // endpoint existed. Left as a real call (rather than removed) so the
      // panel starts working the moment that endpoint is added.
      const res = await api.post<{ projectedNavChange?: number; projectedPnl?: number }>(
        `/v4/portfolios/${portfolioId}/what-if`,
        { scenario: whatIfScenario },
      );
      setWhatIfResults(res);
    } catch (e) {
      console.error('What-if analysis failed', e);
      useToastStore.getState().showToast('What-if analysis is unavailable right now.');
    } finally {
      setWhatIfRunning(false);
    }
  }, [portfolioId, whatIfScenario]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '16px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {activePortfolio.name}
        </h1>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            {formatCurrency(activePortfolio.nav)}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-md)', color: signalColor(activePortfolio.dayChange) }}>
            {formatPct(activePortfolio.dayChange)} ({activePortfolio.dayChangeDollar >= 0 ? '+' : ''}{formatCurrency(activePortfolio.dayChangeDollar)})
          </span>
        </div>
        <span style={{ ...labelStyle }}>Inception: <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{activePortfolio.inception}</span></span>
        <button
          style={{ marginLeft: 'auto', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', background: 'var(--color-accent-primary)', border: 'none', borderRadius: '3px', padding: '6px 14px', cursor: 'pointer' }}
          onClick={() => setShowExport(true)}
        >
          Export Report
        </button>
      </div>

      <ReportExportModal isOpen={showExport} onClose={() => setShowExport(false)} portfolioId={portfolioId} />

      {/* Performance Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activePerfMetrics.map((m) => (
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
              {activeHoldings.map((h) => (
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
              data={activeAllocations}
              height={240}
              centerLabel="Sectors"
              centerValue={String(activeAllocations.length)}
              showLegend
            />
          </div>

          {/* NAV History (30 days) */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>NAV History (30D)</h2>
            <NavHistoryChart data={apiNavHistory?.history.map((h) => ({ date: h.date, value: h.nav }))} />
          </div>

          {/* Portfolio Summary */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Summary</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { label: 'Total Positions', value: String(activeHoldings.length) },
                { label: 'Total Market Value', value: formatCurrency(activeHoldings.reduce((s, h) => s + h.marketValue, 0)) },
                { label: 'Total Unrealized P&L', value: formatCurrency(activeHoldings.reduce((s, h) => s + h.unrealizedPnl, 0)) },
                { label: 'Largest Position', value: activeHoldings.length > 0 ? `${activeHoldings.reduce((max, h) => h.weight > max.weight ? h : max, activeHoldings[0]!).ticker} (${activeHoldings.reduce((max, h) => h.weight > max.weight ? h : max, activeHoldings[0]!).weight.toFixed(1)}%)` : 'N/A' },
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

      {/* Add Position Button */}
      <div style={{ marginTop: 'var(--panel-gap)' }}>
        <button
          onClick={() => setShowAddPosition(true)}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            padding: '8px 16px',
            background: 'var(--color-accent-primary)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Add Position
        </button>
      </div>

      {/* Add Position Modal */}
      {showAddPosition && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowAddPosition(false)}
        >
          <div
            style={{
              ...panelStyle,
              minWidth: '340px',
              maxWidth: '420px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={sectionTitle}>Add Position</h2>
            <label style={labelStyle}>
              Ticker
              <input
                type="text"
                value={positionTicker}
                onChange={(e) => setPositionTicker(e.target.value.toUpperCase())}
                style={{
                  display: 'block',
                  width: '100%',
                  marginTop: '4px',
                  padding: '6px 8px',
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-sm)',
                  background: 'var(--color-surface-base)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-surface-border)',
                  borderRadius: '3px',
                  boxSizing: 'border-box',
                }}
              />
            </label>
            <label style={labelStyle}>
              Shares
              <input
                type="number"
                value={positionShares}
                onChange={(e) => setPositionShares(e.target.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  marginTop: '4px',
                  padding: '6px 8px',
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-sm)',
                  background: 'var(--color-surface-base)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-surface-border)',
                  borderRadius: '3px',
                  boxSizing: 'border-box',
                }}
              />
            </label>
            <label style={labelStyle}>
              Price
              <input
                type="number"
                step="0.01"
                value={positionPrice}
                onChange={(e) => setPositionPrice(e.target.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  marginTop: '4px',
                  padding: '6px 8px',
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-sm)',
                  background: 'var(--color-surface-base)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-surface-border)',
                  borderRadius: '3px',
                  boxSizing: 'border-box',
                }}
              />
            </label>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '4px' }}>
              <button
                onClick={() => setShowAddPosition(false)}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  padding: '6px 14px',
                  background: 'transparent',
                  color: 'var(--color-text-secondary)',
                  border: '1px solid var(--color-surface-border)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleAddPosition}
                disabled={positionSubmitting || !positionTicker || !positionShares || !positionPrice}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  padding: '6px 14px',
                  background: 'var(--color-accent-primary)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: positionSubmitting ? 'wait' : 'pointer',
                  opacity: positionSubmitting || !positionTicker || !positionShares || !positionPrice ? 0.5 : 1,
                }}
              >
                {positionSubmitting ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* What-If Analysis Panel */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>What-If Analysis</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <label style={labelStyle}>
            Scenario
            <select
              value={whatIfScenario}
              onChange={(e) => setWhatIfScenario(e.target.value)}
              style={{
                marginLeft: '8px',
                padding: '6px 8px',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                background: 'var(--color-surface-base)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-surface-border)',
                borderRadius: '3px',
              }}
            >
              <option value="market_drop_10">Market Drop -10%</option>
              <option value="rate_hike_100bp">Rate Hike +100bp</option>
              <option value="sector_rotation">Sector Rotation</option>
            </select>
          </label>
          <button
            onClick={handleRunScenario}
            disabled={whatIfRunning}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 14px',
              background: 'var(--color-accent-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: whatIfRunning ? 'wait' : 'pointer',
              opacity: whatIfRunning ? 0.5 : 1,
            }}
          >
            {whatIfRunning ? 'Running...' : 'Run Scenario'}
          </button>
        </div>
        {whatIfResults && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginTop: '12px' }}>
            <div style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
              <div style={{ ...labelStyle, marginBottom: '4px' }}>Projected NAV Change</div>
              <div style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-lg)',
                fontWeight: 600,
                color: signalColor(whatIfResults.projectedNavChange ?? 0),
              }}>
                {formatPct(whatIfResults.projectedNavChange ?? 0)}
              </div>
            </div>
            <div style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
              <div style={{ ...labelStyle, marginBottom: '4px' }}>Projected P&L</div>
              <div style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-lg)',
                fontWeight: 600,
                color: signalColor(whatIfResults.projectedPnl ?? 0),
              }}>
                {formatCurrency(whatIfResults.projectedPnl ?? 0)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
