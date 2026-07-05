// ---------------------------------------------------------------------------
// Quant Dashboard — Factor Performance, Momentum Signals, Volatility Surface
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCorrelation, useFactorExposure, useTechnicalSignals } from '@/hooks';
import { useSecurityStore } from '@/stores/securityContext';

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

// --- Empty / placeholder data (P4-F-019) -------------------------------------
// We avoid hardcoded factor / momentum / vol-surface defaults: the
// previous values surfaced specific tickers (NVDA, TSLA, etc.) and
// fabricated implied vols via ``Math.abs(strikeIdx - 3) * 2.5`` that
// users couldn't distinguish from real data. Empty arrays render an
// empty table; live API data fills the panels.

const factorPerformance: { factor: string; mtd: number; qtd: number; ytd: number; oneYear: number; sharpe: number; ic: number }[] = [];

const momentumSignals: { ticker: string; name: string; score: number; signal: string; priceReturn: number; rsi: number; macd: string }[] = [];

interface VolSurfacePoint {
  tenor: string;
  moneyness: string;
  iv: number;
}

const volSurface: VolSurfacePoint[] = [];

function scoreColor(score: number): string {
  if (score >= 80) return 'var(--color-signal-positive)';
  if (score >= 50) return 'var(--color-signal-neutral)';
  if (score >= 30) return 'var(--color-quality-2)';
  return 'var(--color-signal-negative)';
}

function signalBg(signal: string): string {
  if (signal.includes('Strong Buy')) return 'color-mix(in srgb, var(--color-signal-positive) 15%, transparent)';
  if (signal.includes('Buy')) return 'color-mix(in srgb, var(--color-signal-positive) 10%, transparent)';
  if (signal.includes('Strong Sell')) return 'color-mix(in srgb, var(--color-signal-negative) 15%, transparent)';
  if (signal.includes('Sell')) return 'color-mix(in srgb, var(--color-signal-negative) 10%, transparent)';
  return 'transparent';
}

// --- Component ---------------------------------------------------------------

export default function QuantDashboard() {
  const navigate = useNavigate();
  const [selectedTenor, setSelectedTenor] = useState('3M');

  const primary = useSecurityStore((s) => s.primary);
  const secId = primary?.security_id;

  const { data: apiCorrelation } = useCorrelation() as { data: any };
  const { data: apiFactors } = useFactorExposure(secId) as { data: any };
  const { data: apiSignals } = useTechnicalSignals(secId) as { data: any };

  const activeFactorPerf = (apiFactors as any)?.factors ?? (apiCorrelation as any)?.factorPerformance ?? factorPerformance;
  const activeMomentum = (apiSignals as any)?.signals ?? momentumSignals;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Quant Dashboard {primary && `— ${primary.name} (${primary.ticker})`}
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Factor performance, momentum signals, and volatility surface analysis</p>
      </div>

      {/* Factor Performance Table */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Factor Performance</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Factor', 'MTD', 'QTD', 'YTD', '1Y', 'Sharpe', 'IC'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Factor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeFactorPerf.map((f: any) => (
              <tr key={f.factor} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.factor}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(f.mtd) }}>{f.mtd >= 0 ? '+' : ''}{f.mtd.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(f.qtd) }}>{f.qtd >= 0 ? '+' : ''}{f.qtd.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(f.ytd) }}>{f.ytd >= 0 ? '+' : ''}{f.ytd.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(f.oneYear), fontWeight: 600 }}>{f.oneYear >= 0 ? '+' : ''}{f.oneYear.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(f.sharpe) }}>{f.sharpe.toFixed(2)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.ic.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Momentum Signals */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Momentum Signals</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Ticker', 'Score', 'Signal', '3M Return', 'RSI', 'MACD'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Ticker' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeMomentum.map((s: any) => (
                <tr key={s.ticker} style={{ height: 'var(--table-row-height)', background: signalBg(s.signal) }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{s.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: scoreColor(s.score), fontWeight: 600 }}>{s.score}</td>
                  <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: scoreColor(s.score),
                      fontWeight: 600,
                    }}>
                      {s.signal}
                    </span>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.priceReturn) }}>{s.priceReturn >= 0 ? '+' : ''}{s.priceReturn.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.rsi}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: s.macd === 'Bullish' ? 'var(--color-signal-positive)' : s.macd === 'Bearish' ? 'var(--color-signal-negative)' : 'var(--color-text-secondary)' }}>{s.macd}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Volatility Surface Placeholder */}
        <div style={panelStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <h2 style={{ ...sectionTitle, margin: 0 }}>Implied Volatility Surface (SPX)</h2>
            <span style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: '3px',
              background: 'color-mix(in srgb, var(--color-quality-2) 20%, transparent)',
              color: 'var(--color-quality-2)',
              border: '1px solid color-mix(in srgb, var(--color-quality-2) 40%, transparent)',
              whiteSpace: 'nowrap',
            }}>
              Illustrative — not from live data
            </span>
          </div>
          <div style={{ display: 'flex', gap: '4px', marginBottom: '12px' }}>
            {tenors.map((t) => (
              <button
                key={t}
                onClick={() => setSelectedTenor(t)}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: selectedTenor === t ? 600 : 400,
                  background: selectedTenor === t ? 'var(--color-surface-overlay)' : 'transparent',
                  color: selectedTenor === t ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)',
                }}
              >
                {t}
              </button>
            ))}
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Strike</th>
                <th style={{ ...labelStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>IV (%)</th>
              </tr>
            </thead>
            <tbody>
              {volSurface
                .filter((p) => p.tenor === selectedTenor)
                .map((p) => (
                  <tr key={p.moneyness} style={{ height: 'var(--table-row-height)', background: p.moneyness === '100%' ? 'var(--color-surface-overlay)' : 'transparent' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: p.moneyness === '100%' ? 600 : 400 }}>{p.moneyness}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.iv.toFixed(1)}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Backtester Link */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={sectionTitle}>Strategy Backtester</h2>
          <p style={{ ...labelStyle, margin: 0 }}>Build, test, and compare quantitative strategies with historical data</p>
        </div>
        <span
          onClick={() => navigate('/quant/backtest')}
          style={{
            fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: '8px 20px', borderRadius: '4px',
            background: 'var(--color-accent-primary)', color: 'var(--color-text-inverse)',
            cursor: 'pointer', userSelect: 'none', fontWeight: 600,
          }}
        >Open Backtester</span>
      </div>
    </div>
  );
}
