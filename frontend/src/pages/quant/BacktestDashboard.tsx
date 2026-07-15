// ---------------------------------------------------------------------------
// Backtest Dashboard — Strategy Backtesting, Results & History
// ---------------------------------------------------------------------------
import { useState, useCallback, useEffect } from 'react';
import { useBacktestStrategies } from '@/hooks';
import { api } from '@/api/client';
import { BACKTESTING } from '@/api/endpoints';

interface BacktestStrategyOption {
  strategy_id: string;
  name: string;
  description?: string | null;
  tags?: string[];
  strategy_definition?: Record<string, unknown>;
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

// --- Empty fallback (P4-F-017) -----------------------------------------------
// Default strategies / backtest results / recent runs are now empty so
// users see a true "nothing to show" state instead of fabricated CAGR /
// Sharpe figures attributed to specific strategies. Live data populates
// the lists when the API returns rows.

const strategies: BacktestStrategyOption[] = [];
const backtestResults: { strategy: string; period: string; cagr: number; sharpe: number; maxDrawdown: number; winRate: number; alpha: number }[] = [];
const recentBacktests: { id: string; strategy: string; ranAt: string; status: string; cagr: number | null; sharpe: number | null }[] = [];

const kpiData = [
  { label: 'Strategies', value: '6' },
  { label: 'Backtests Run', value: '142' },
  { label: 'Best Strategy CAGR', value: '+16.24%', color: 'var(--color-signal-positive)' },
  { label: 'Avg Sharpe', value: '1.08' },
  { label: 'Win Rate', value: '60.1%' },
  { label: 'Max Drawdown', value: '-28.6%', color: 'var(--color-signal-negative)' },
];

const universeOptions = ['S&P 500', 'Russell 1000', 'Russell 2000', 'MSCI World', 'Multi-Asset', 'NASDAQ 100'];

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-sm)',
  padding: '6px 10px',
  borderRadius: '4px',
  border: '1px solid var(--color-surface-border)',
  background: 'var(--color-surface-overlay)',
  color: 'var(--color-text-primary)',
  outline: 'none',
  width: '100%',
};

// --- Component ---------------------------------------------------------------

export default function BacktestDashboard() {
  // [Bug 93 fix] No fabricated default -- real strategy names come from
  // GET /v2/analytics/backtest/strategies (src/api/routers/backtesting.py,
  // reusing the E4 prebuilt-screen library), so the selection starts empty
  // and is set once real options load (below).
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [universe, setUniverse] = useState('S&P 500');
  const [startDate, setStartDate] = useState('2019-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');

  const { data: apiStrategies } = useBacktestStrategies() as { data: BacktestStrategyOption[] | undefined };

  const activeStrategies = apiStrategies ?? strategies;
  const activeResults = backtestResults; // Mocked until backend has true backtesting
  // [P4-F-017 fix] No "list all backtest runs" endpoint exists anywhere in
  // backtesting.py -- useBacktestHistory always fired against a path that
  // 404s. Recent runs stay an honest empty state until that endpoint exists.
  const activeHistory = recentBacktests;

  // Default the selector to the first real strategy once the library loads.
  useEffect(() => {
    const first = activeStrategies[0];
    if (!selectedStrategy && first) {
      setSelectedStrategy(first.name);
    }
  }, [activeStrategies, selectedStrategy]);

  // Dynamic KPIs (Bug 91 fix)
  // [P4-F-017 fix] Guard against an empty `activeResults` array -- it was
  // permanently empty (mocked until the backend has true backtesting, see
  // comment above), so `.reduce()` with `activeResults[0]` as the seed
  // produced `undefined`, rendering as the literal strings "+undefined%"
  // and "NaN%" instead of an honest empty/placeholder state.
  const totalStrategies = activeStrategies?.length ?? 0;
  const totalBacktests = activeHistory?.length ?? 0;
  const hasResults = activeResults.length > 0;
  const bestResult = hasResults
    ? activeResults.reduce((max, r) => (r.cagr > max.cagr ? r : max), activeResults[0]!)
    : null;
  const avgSharpe = hasResults
    ? activeResults.reduce((sum, r) => sum + r.sharpe, 0) / activeResults.length
    : null;
  const avgWinRate = hasResults
    ? activeResults.reduce((sum, r) => sum + r.winRate, 0) / activeResults.length
    : null;
  const maxDrawdownObj = hasResults
    ? activeResults.reduce((min, r) => (r.maxDrawdown < min.maxDrawdown ? r : min), activeResults[0]!)
    : null;

  const dynamicKpis = [
    { label: 'Strategies', value: totalStrategies.toString() },
    { label: 'Backtests Run', value: totalBacktests.toString() },
    {
      label: 'Best Strategy CAGR',
      value: bestResult ? `+${bestResult.cagr.toFixed(2)}%` : '—',
      color: bestResult ? 'var(--color-signal-positive)' : undefined,
    },
    { label: 'Avg Sharpe', value: avgSharpe != null ? avgSharpe.toFixed(2) : '—' },
    { label: 'Win Rate', value: avgWinRate != null ? `${avgWinRate.toFixed(1)}%` : '—' },
    {
      label: 'Max Drawdown',
      value: maxDrawdownObj ? `${maxDrawdownObj.maxDrawdown.toFixed(1)}%` : '—',
      color: maxDrawdownObj ? 'var(--color-signal-negative)' : undefined,
    },
  ];

  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleRunBacktest = useCallback(async () => {
    setIsRunning(true);
    setRunError(null);
    try {
      // [P4-F-017 fix] POST /v1/analytics/backtest (src/api/routers/
      // backtesting.py) expects a BacktestRequest body -- name +
      // strategy_definition (the selected prebuilt screen's filter
      // criteria) + start_date/end_date, not the ad-hoc
      // {strategy, universe, startDate, endDate} shape this used to send
      // (which would 422 even once the path was fixed). The run is queued
      // PENDING; there is no scheduler wired up yet to advance it (see the
      // endpoint's docstring), so this intentionally doesn't poll for a
      // result.
      const selected = activeStrategies.find((s) => s.name === selectedStrategy);
      await api.post(BACKTESTING.run, {
        name: selected?.name ?? selectedStrategy,
        description: universe ? `Universe: ${universe}` : undefined,
        strategy_definition: selected?.strategy_definition ?? {},
        start_date: startDate,
        end_date: endDate,
      });
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Backtest failed. Please try again.');
    } finally {
      setIsRunning(false);
    }
  }, [activeStrategies, selectedStrategy, universe, startDate, endDate]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Backtest Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Strategy backtesting, performance analysis, and historical results</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {dynamicKpis.map((kpi) => (
          <div key={kpi.label} style={panelStyle}>
            <div style={labelStyle}>{kpi.label}</div>
            <div style={{ ...dataStyle, fontSize: 'var(--text-lg)', fontWeight: 600, marginTop: '4px', color: kpi.color ?? 'var(--color-text-primary)' }}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* Strategy Configuration */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Strategy Configuration</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: '16px', alignItems: 'end' }}>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Strategy Name</label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              style={inputStyle}
            >
              {activeStrategies.map((s) => (
                <option key={s.strategy_id ?? s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Universe</label>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              style={inputStyle}
            >
              {universeOptions.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={inputStyle}
            />
          </div>
          <button
            onClick={handleRunBacktest}
            disabled={isRunning}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '8px 20px',
              borderRadius: '4px',
              border: 'none',
              cursor: isRunning ? 'wait' : 'pointer',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-surface-base)',
              whiteSpace: 'nowrap',
              opacity: isRunning ? 0.7 : 1,
            }}
          >
            {isRunning ? 'Running…' : 'Run Backtest'}
          </button>
        </div>
        {runError && (
          <div style={{ marginTop: '8px', padding: '6px 10px', borderRadius: '4px', background: 'color-mix(in srgb, var(--color-signal-negative) 10%, transparent)', color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)' }}>
            {runError}
          </div>
        )}
      </div>

      {/* Backtest Results Table */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Backtest Results</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Strategy', 'Period', 'CAGR %', 'Sharpe', 'Max Drawdown %', 'Win Rate %', 'Alpha %'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Strategy' || h === 'Period' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeResults.map((r: any, idx: number) => (
              <tr key={`${r.strategy}-${r.period}-${idx}`} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, color: 'var(--color-accent-primary)' }}>{r.strategy}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.period}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.cagr), fontWeight: 600 }}>{r.cagr >= 0 ? '+' : ''}{r.cagr.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.sharpe) }}>{r.sharpe.toFixed(2)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)', fontWeight: 600 }}>{r.maxDrawdown.toFixed(1)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.winRate.toFixed(1)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(r.alpha), fontWeight: 600 }}>{r.alpha >= 0 ? '+' : ''}{r.alpha.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent Backtests History */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>Recent Backtests</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Strategy', 'Run At', 'Status', 'CAGR %', 'Sharpe'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Strategy' || h === 'Run At' || h === 'Status' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeHistory.map((b: any) => (
              <tr key={b.id} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{b.strategy}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{b.ranAt}</td>
                <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    padding: '1px 6px',
                    borderRadius: '2px',
                    fontWeight: 600,
                    color: b.status === 'Completed' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)',
                  }}>
                    {b.status}
                  </span>
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: b.cagr != null ? signalColor(b.cagr) : 'var(--color-text-secondary)', fontWeight: 600 }}>
                  {b.cagr != null ? `${b.cagr >= 0 ? '+' : ''}${b.cagr.toFixed(2)}%` : '--'}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: b.sharpe != null ? signalColor(b.sharpe) : 'var(--color-text-secondary)' }}>
                  {b.sharpe != null ? b.sharpe.toFixed(2) : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
