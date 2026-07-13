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

type BriefingMeta = { date?: string; time?: string; confidence?: number };
type MarketContextItem = { label: string; value: string };
type BriefingTheme = { theme: string; impact: string; tickers: string[]; detail: string };
type PortfolioImpactItem = { ticker: string; weight?: number; impact: string; reason: string };
type BriefingHistoryItem = { id?: string; date?: string; title?: string; summary?: string; confidence?: number };
type BriefingPayload = {
  meta?: BriefingMeta;
  marketContext?: MarketContextItem[];
  themes?: BriefingTheme[];
  portfolioImpact?: PortfolioImpactItem[];
};
type BriefingHistoryPayload = { briefings?: BriefingHistoryItem[] };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object';

const briefingPayload = (value: unknown): BriefingPayload =>
  isRecord(value) ? (value as BriefingPayload) : {};

const historyPayload = (value: unknown): BriefingHistoryItem[] => {
  if (Array.isArray(value)) return value as BriefingHistoryItem[];
  if (isRecord(value) && Array.isArray(value.briefings)) return value.briefings as BriefingHistoryItem[];
  return [];
};

export default function BriefingView() {
  const { data: apiBriefing, isLoading, isError } = useMorningBriefing();
  const { data: apiHistory } = useBriefingHistory();
  const [generating, setGenerating] = useState(false);

  const payload = briefingPayload(apiBriefing);
  const activeMeta = payload.meta ?? {};
  const activeContext = payload.marketContext ?? [];
  const activeThemes = payload.themes ?? [];
  const activeImpact = payload.portfolioImpact ?? [];
  const briefingHistory = historyPayload(apiHistory as BriefingHistoryPayload | BriefingHistoryItem[] | undefined);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await api.post(RESEARCH.briefings.generate, {});
    } catch (error) {
      console.error('Failed to generate briefing:', error);
    }
    setGenerating(false);
  };

  if (isLoading) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Morning Briefing</h1>
      <p style={{ ...labelStyle, marginTop: '12px' }}>Loading briefing data...</p>
    </div>
  );

  if (isError) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Morning Briefing</h1>
      <p style={{ ...labelStyle, marginTop: '12px', color: 'var(--color-signal-negative)' }}>Failed to load briefing data.</p>
    </div>
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Morning Briefing</h1>
        <span style={labelStyle}>{activeMeta.date ?? "No briefing date"} &mdash; {activeMeta.time ?? "—"}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)' }}>AI Confidence: {activeMeta.confidence != null ? `${activeMeta.confidence}%` : "—"}</span>
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
            {activeThemes.length === 0 ? (
              <p style={labelStyle}>No briefing themes available.</p>
            ) : activeThemes.map((t) => (
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
              {activeImpact.length === 0 ? (
                <tr><td colSpan={4} style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>No portfolio impacts available.</td></tr>
              ) : activeImpact.map((p) => (
                <tr key={p.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{p.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.weight != null ? `${p.weight}%` : "—"}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.impact?.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>{p.impact}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Briefing History */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Briefing History</h2>
        {briefingHistory.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {briefingHistory.map((b, i: number) => (
              <div key={b.id ?? i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div>
                  <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 500 }}>{b.date ?? b.title}</span>
                  {b.summary && (
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>{b.summary}</span>
                  )}
                </div>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{b.confidence != null ? `${b.confidence}%` : ''}</span>
              </div>
            ))}
          </div>
        ) : (
          <p style={labelStyle}>No previous briefings available.</p>
        )}
      </div>
    </div>
  );
}
