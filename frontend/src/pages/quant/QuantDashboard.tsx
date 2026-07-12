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

const momentumSignals: { indicator: string; name: string; value: number; signal: string | null; category: string | null }[] = [];

interface VolSurfacePoint {
  tenor: string;
  moneyness: string;
  iv: number;
}

const volSurface: VolSurfacePoint[] = [];
// Tenor button labels only (no fake IV values are generated from this list —
// see the "Illustrative — not from live data" disclosure below; this
// codebase has no options-chain / implied-vol data source, so the table
// stays empty until one exists).
const tenors = ['1W', '1M', '2M', '3M', '6M', '1Y'];

// --- Component ---------------------------------------------------------------

export default function QuantDashboard() {
  const navigate = useNavigate();
  const [selectedTenor, setSelectedTenor] = useState('3M');

  const primary = useSecurityStore((s) => s.primary);
  const secId = primary?.security_id;

  const { data: apiCorrelation } = useCorrelation() as { data: any };
  const { data: apiFactorExposure } = useFactorExposure(secId) as { data: any };
  const { data: apiSignals } = useTechnicalSignals(secId) as { data: any };

  // Factor Performance table: cross-sectional factor return/IC summary,
  // backed by GET /v2/analytics/correlation (separate scope from this fix).
  const activeFactorPerf = (apiCorrelation as any)?.factorPerformance ?? factorPerformance;

  // Security Factor Exposure (Bug 87): single-factor (CAPM market beta)
  // computed live from real EODPrice data via QuantEngine (E7). This
  // codebase has no factor-return time series, so genuine multi-factor
  // (size/value/momentum) exposure isn't computable here — the backend
  // returns a `note` explaining that instead of fabricating extra factors.
  const securityFactors = (apiFactorExposure as any)?.factors ?? [];
  const factorExposureNote = (apiFactorExposure as any)?.note as string | undefined;

  // Momentum Signals (Bug 87): real per-indicator technical signals
  // (SMA/EMA/RSI/MACD/etc.) for the selected security, computed live from
  // EODPrice via src/engines/technical_studies.py. Same shape/endpoint that
  // CompanyOverview.tsx's "Technical Signals" panel consumes.
  const activeMomentum = (apiSignals as any)?.signals ?? momentumSignals;
  const momentumPrice = (apiSignals as any)?.price as number | undefined;
  const momentumReturn1m = (apiSignals as any)?.priceReturn1m as number | undefined;

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

      {/* Security Factor Exposure (Bug 87) — real, single-factor market beta,
          computed live from EODPrice. No size/value/momentum factor-return
          series exists in this codebase, so only the market factor is shown;
          `factorExposureNote` (from the backend) explains that honestly. */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Security Factor Exposure{primary && ` — ${primary.ticker}`}</h2>
        {securityFactors.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Factor', 'Beta', 'Blume-Adjusted', 'R²', 'Correlation'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Factor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {securityFactors.map((f: any) => (
                <tr key={f.factor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.factor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.exposure?.toFixed(2) ?? '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.blumeAdjusted?.toFixed(2) ?? '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.rSquared?.toFixed(3) ?? '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.correlation?.toFixed(3) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={labelStyle}>{secId ? 'Insufficient price history to compute factor exposure.' : 'Select a security to view its factor exposure.'}</p>
        )}
        {factorExposureNote && (
          <p style={{ ...labelStyle, fontSize: 'var(--text-xs)', marginTop: '8px', fontStyle: 'italic' }}>{factorExposureNote}</p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Momentum Signals — real per-indicator technical signals for the
            selected security, computed live from EODPrice (Bug 87). Same
            endpoint/shape as CompanyOverview.tsx's Technical Signals panel. */}
        <div style={panelStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4px' }}>
            <h2 style={{ ...sectionTitle, margin: 0 }}>Momentum Signals{primary && ` — ${primary.ticker}`}</h2>
            {momentumPrice != null && (
              <span style={labelStyle}>
                {momentumPrice.toFixed(2)}
                {momentumReturn1m != null && (
                  <span style={{ marginLeft: '6px', color: signalColor(momentumReturn1m) }}>
                    {momentumReturn1m >= 0 ? '+' : ''}{momentumReturn1m.toFixed(1)}% (1M)
                  </span>
                )}
              </span>
            )}
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '8px' }}>
            <thead>
              <tr>
                {['Indicator', 'Value', 'Signal'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Indicator' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeMomentum.map((s: any) => (
                <tr key={s.indicator ?? s.name} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.value != null ? s.value.toFixed(2) : '—'}</td>
                  <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 600,
                      color: s.signal === 'Bullish' || s.signal === 'Above' ? 'var(--color-signal-positive)'
                        : s.signal === 'Bearish' || s.signal === 'Below' ? 'var(--color-signal-negative)'
                        : s.signal === 'Overbought' ? 'var(--color-signal-negative)'
                        : s.signal === 'Oversold' ? 'var(--color-signal-positive)'
                        : 'var(--color-text-secondary)',
                    }}>
                      {s.signal ?? '—'}
                    </span>
                  </td>
                </tr>
              ))}
              {activeMomentum.length === 0 && (
                <tr>
                  <td colSpan={3} style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', textAlign: 'center' }}>
                    {secId ? 'Insufficient price history to compute technical signals.' : 'Select a security to view its momentum signals.'}
                  </td>
                </tr>
              )}
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
