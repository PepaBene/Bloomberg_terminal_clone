// ---------------------------------------------------------------------------
// Briefing View — Morning Briefing Detail
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useMorningBriefing, useBriefingHistory } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const briefingMeta = { date: 'March 27, 2026', time: '06:30 ET', confidence: 92 };

const marketContext = [
  { label: 'S&P 500 Futures', value: '+0.35%' },
  { label: 'UST 10Y', value: '4.28% (-3bps)' },
  { label: 'VIX', value: '17.8 (-1.2)' },
  { label: 'DXY', value: '103.42 (-0.15)' },
];

const keyThemes = [
  { theme: 'AI Infrastructure Spend Accelerating', impact: 'Positive', tickers: ['NVDA', 'AVGO', 'AMD'], detail: 'Hyperscaler CapEx guidance raised across board; NVDA data center revenue up 122% YoY' },
  { theme: 'Fed Patience Narrative Strengthening', impact: 'Mixed', tickers: ['TLT', 'XLF'], detail: 'Powell reiterated no rush to cut; June pricing at 42% probability' },
  { theme: 'Consumer Softening Signals', impact: 'Negative', tickers: ['XLY', 'WMT', 'TGT'], detail: 'Jobless claims rising; consumer sentiment declining for 3rd consecutive month' },
];

const portfolioImpact = [
  { ticker: 'NVDA', weight: 8.2, impact: '+0.42%', reason: 'AI theme — data center beat' },
  { ticker: 'AAPL', weight: 6.5, impact: '-0.08%', reason: 'iPhone seasonality weakness' },
  { ticker: 'JPM', weight: 4.2, impact: '-0.12%', reason: 'CDS widening; credit concern' },
  { ticker: 'TLT', weight: 3.8, impact: '+0.15%', reason: 'Duration rally on dovish shift' },
];

export default function BriefingView() {
  const { data: apiBriefing } = useMorningBriefing() as { data: any };
  const { data: apiHistory } = useBriefingHistory() as { data: any };
  const [generating, setGenerating] = useState(false);

  const activeMeta = (apiBriefing as any)?.meta ?? briefingMeta;
  const activeContext = (apiBriefing as any)?.marketContext ?? marketContext;
  const activeThemes = (apiBriefing as any)?.themes ?? keyThemes;
  const activeImpact = (apiBriefing as any)?.portfolioImpact ?? portfolioImpact;

  const handleGenerate = async () => {
    setGenerating(true);
    try { await api.post(RESEARCH.briefings.generate, {}); } catch {}
    setGenerating(false);
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Morning Briefing</h1>
        <span style={labelStyle}>{activeMeta.date} &mdash; {activeMeta.time}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)' }}>AI Confidence: {activeMeta.confidence}%</span>
        <button className="btn-primary" onClick={handleGenerate} disabled={generating} style={{ marginLeft: '8px' }}>
          {generating ? 'Generating…' : 'Generate Briefing'}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeContext.map((m) => (
          <div key={m.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{m.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{m.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Key Themes</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeThemes.map((t) => (
              <div key={t.theme} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{t.theme}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: t.impact === 'Positive' ? 'var(--color-signal-positive)' : t.impact === 'Negative' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{t.impact}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>{t.detail}</div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {t.tickers.map((tk) => (
                    <span key={tk} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', background: 'var(--color-surface-base)', padding: '1px 4px', borderRadius: '2px' }}>{tk}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Portfolio Impact</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Ticker', 'Weight', 'Impact', 'Reason'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Reason' ? 'left' : h === 'Ticker' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeImpact.map((p) => (
                <tr key={p.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{p.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.weight}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.impact.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>{p.impact}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
