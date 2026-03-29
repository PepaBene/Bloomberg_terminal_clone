// ---------------------------------------------------------------------------
// Quant Dashboard — Factor Performance, Momentum Signals, Volatility Surface
// ---------------------------------------------------------------------------
import { useState } from 'react';

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

const factorPerformance = [
  { factor: 'Value (HML)',         mtd: 1.82,  qtd: 3.45,  ytd: 5.12,  oneYear: 8.24,  sharpe: 0.62, ic: 0.045 },
  { factor: 'Size (SMB)',          mtd: -0.54, qtd: -1.22, ytd: -2.18, oneYear: -3.84, sharpe: -0.28, ic: 0.012 },
  { factor: 'Momentum (MOM)',      mtd: 2.14,  qtd: 5.68,  ytd: 9.42,  oneYear: 14.28, sharpe: 0.84, ic: 0.068 },
  { factor: 'Quality (RMW)',       mtd: 0.92,  qtd: 2.18,  ytd: 4.56,  oneYear: 7.82,  sharpe: 0.72, ic: 0.052 },
  { factor: 'Low Volatility',     mtd: 0.38,  qtd: 1.24,  ytd: 3.28,  oneYear: 6.14,  sharpe: 0.58, ic: 0.038 },
  { factor: 'Investment (CMA)',    mtd: -0.18, qtd: 0.42,  ytd: 1.86,  oneYear: 3.52,  sharpe: 0.34, ic: 0.028 },
  { factor: 'Profitability',      mtd: 1.42,  qtd: 3.86,  ytd: 6.24,  oneYear: 10.18, sharpe: 0.76, ic: 0.058 },
  { factor: 'Earnings Revision',  mtd: 1.68,  qtd: 4.12,  ytd: 7.86,  oneYear: 12.42, sharpe: 0.82, ic: 0.064 },
];

const momentumSignals = [
  { ticker: 'NVDA',  name: 'NVIDIA Corp.',       score: 94, signal: 'Strong Buy',  priceReturn: 42.8,  rsi: 72, macd: 'Bullish' },
  { ticker: 'AVGO',  name: 'Broadcom Inc.',      score: 88, signal: 'Buy',         priceReturn: 28.4,  rsi: 68, macd: 'Bullish' },
  { ticker: 'META',  name: 'Meta Platforms',       score: 85, signal: 'Buy',         priceReturn: 22.6,  rsi: 64, macd: 'Bullish' },
  { ticker: 'LLY',   name: 'Eli Lilly',           score: 82, signal: 'Buy',         priceReturn: 18.2,  rsi: 62, macd: 'Bullish' },
  { ticker: 'AMZN',  name: 'Amazon.com',          score: 78, signal: 'Buy',         priceReturn: 15.8,  rsi: 58, macd: 'Neutral' },
  { ticker: 'TSLA',  name: 'Tesla Inc.',           score: 22, signal: 'Sell',        priceReturn: -24.6, rsi: 32, macd: 'Bearish' },
  { ticker: 'PFE',   name: 'Pfizer Inc.',          score: 18, signal: 'Strong Sell', priceReturn: -18.2, rsi: 28, macd: 'Bearish' },
  { ticker: 'BA',    name: 'Boeing Co.',           score: 15, signal: 'Strong Sell', priceReturn: -32.4, rsi: 24, macd: 'Bearish' },
];

interface VolSurfacePoint {
  tenor: string;
  moneyness: string;
  iv: number;
}

const volSurface: VolSurfacePoint[] = [];
const tenors = ['1W', '1M', '2M', '3M', '6M', '1Y'];
const strikes = ['80%', '90%', '95%', '100%', '105%', '110%', '120%'];
for (const tenor of tenors) {
  for (const strike of strikes) {
    const tenorIdx = tenors.indexOf(tenor);
    const strikeIdx = strikes.indexOf(strike);
    const baseVol = 22 + tenorIdx * 1.5;
    const skew = Math.abs(strikeIdx - 3) * 2.5 + (strikeIdx < 3 ? (3 - strikeIdx) * 1.2 : 0);
    volSurface.push({ tenor, moneyness: strike, iv: Math.round((baseVol + skew) * 10) / 10 });
  }
}

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
  const [selectedTenor, setSelectedTenor] = useState('3M');

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Quant Dashboard
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
            {factorPerformance.map((f) => (
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
              {momentumSignals.map((s) => (
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
          <h2 style={sectionTitle}>Implied Volatility Surface (SPX)</h2>
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
    </div>
  );
}
