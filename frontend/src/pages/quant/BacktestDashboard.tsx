// ---------------------------------------------------------------------------
// Backtest Dashboard — Strategy Backtesting, Results & History
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useBacktestStrategies, useBacktestHistory } from '@/hooks';
import { api } from '@/api/client';
import { BACKTESTING } from '@/api/endpoints';

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

// --- Mock Data ---------------------------------------------------------------

const strategies = [
  { id: 'strat-1', name: 'Momentum Long/Short', universe: 'S&P 500', rebalance: 'Monthly' },
  { id: 'strat-2', name: 'Value Factor Tilt', universe: 'Russell 1000', rebalance: 'Quarterly' },
  { id: 'strat-3', name: 'Min Variance', universe: 'MSCI World', rebalance: 'Monthly' },
  { id: 'strat-4', name: 'Quality + Momentum', universe: 'S&P 500', rebalance: 'Monthly' },
  { id: 'strat-5', name: 'Risk Parity', universe: 'Multi-Asset', rebalance: 'Weekly' },
  { id: 'strat-6', name: 'Earnings Revision Alpha', universe: 'Russell 2000', rebalance: 'Monthly' },
];

const backtestResults = [
  { strategy: 'Momentum Long/Short', period: '2019-2024', cagr: 14.82, sharpe: 1.24, maxDrawdown: -18.4, winRate: 62.3, alpha: 6.12 },
  { strategy: 'Value Factor Tilt',   period: '2019-2024', cagr: 9.45,  sharpe: 0.78, maxDrawdown: -24.8, winRate: 55.8, alpha: 2.34 },
  { strategy: 'Min Variance',        period: '2019-2024', cagr: 7.62,  sharpe: 0.92, maxDrawdown: -12.6, winRate: 58.4, alpha: 1.18 },
  { strategy: 'Quality + Momentum',  period: '2019-2024', cagr: 16.24, sharpe: 1.38, maxDrawdown: -16.2, winRate: 64.1, alpha: 7.86 },
  { strategy: 'Risk Parity',         period: '2019-2024', cagr: 8.18,  sharpe: 1.04, maxDrawdown: -10.8, winRate: 60.2, alpha: 1.92 },
  { strategy: 'Earnings Revision Alpha', period: '2019-2024', cagr: 12.56, sharpe: 1.12, maxDrawdown: -20.4, winRate: 59.6, alpha: 4.84 },
  { strategy: 'Momentum Long/Short', period: '2015-2024', cagr: 12.38, sharpe: 1.08, maxDrawdown: -28.6, winRate: 60.1, alpha: 4.92 },
  { strategy: 'Quality + Momentum',  period: '2015-2024', cagr: 14.86, sharpe: 1.22, maxDrawdown: -22.4, winRate: 62.8, alpha: 6.48 },
];

const recentBacktests = [
  { id: 'bt-1', strategy: 'Quality + Momentum', ranAt: '2026-04-02 09:14:22', status: 'Completed', cagr: 16.24, sharpe: 1.38 },
  { id: 'bt-2', strategy: 'Momentum Long/Short', ranAt: '2026-04-01 16:42:08', status: 'Completed', cagr: 14.82, sharpe: 1.24 },
  { id: 'bt-3', strategy: 'Risk Parity', ranAt: '2026-04-01 11:28:54', status: 'Completed', cagr: 8.18, sharpe: 1.04 },
  { id: 'bt-4', strategy: 'Value Factor Tilt', ranAt: '2026-03-31 14:56:12', status: 'Completed', cagr: 9.45, sharpe: 0.78 },
  { id: 'bt-5', strategy: 'Min Variance', ranAt: '2026-03-31 10:22:38', status: 'Failed', cagr: null, sharpe: null },
  { id: 'bt-6', strategy: 'Earnings Revision Alpha', ranAt: '2026-03-30 15:08:44', status: 'Completed', cagr: 12.56, sharpe: 1.12 },
];

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
  const [selectedStrategy, setSelectedStrategy] = useState('Momentum Long/Short');
  const [universe, setUniverse] = useState('S&P 500');
  const [startDate, setStartDate] = useState('2019-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');

  const { data: apiStrategies } = useBacktestStrategies() as { data: any };
  const { data: apiHistory } = useBacktestHistory() as { data: any };

  const activeStrategies = (apiStrategies as any)?.strategies ?? strategies;
  const activeResults = (apiStrategies as any)?.results ?? backtestResults;
  const activeHistory = (apiHistory as any)?.history ?? recentBacktests;

  const handleRunBacktest = useCallback(async () => {
    try { await api.post(BACKTESTING.run, { strategy: selectedStrategy, universe, startDate, endDate }); } catch {}
  }, [selectedStrategy, universe, startDate, endDate]);

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
        {kpiData.map((kpi) => (
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
              {activeStrategies.map((s: any) => (
                <option key={s.id ?? s.name} value={s.name}>{s.name}</option>
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
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '8px 20px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-surface-base)',
              whiteSpace: 'nowrap',
            }}
          >
            Run Backtest
          </button>
        </div>
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
