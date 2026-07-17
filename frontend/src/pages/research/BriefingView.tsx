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

// Mirrors `MorningBriefingResponse` (src/schemas/morning_briefing_schema.py:8) —
// there is no `meta`/`marketContext`/`themes`/`portfolioImpact` wrapper on
// the real response, and no "themes" concept exists in the backend at all.
interface MacroContextEntry { name: string; value: number; observation_date: string; yoy_change_pct: number | null }
interface PortfolioImpactEntry { entity_name: string; price_change_1d_pct: number }
interface ThesisUpdate { entity_id: string; thesis_title: string | null; conviction_level: string | null; version: number; updated_at: string | null }
interface MorningBriefingApi {
  id: string;
  briefing_date: string;
  executive_summary: string | null;
  portfolio_impact: Record<string, PortfolioImpactEntry> | null;
  thesis_updates: { updates: ThesisUpdate[] } | null;
  macro_context: Record<string, MacroContextEntry> | null;
  ai_enabled: boolean;
}

export default function BriefingView() {
  const { data: apiBriefing, isLoading, isError } = useMorningBriefing();
  const { data: apiHistory } = useBriefingHistory();
  const [generating, setGenerating] = useState(false);

  const briefing = apiBriefing as MorningBriefingApi | undefined;
  const macroContext = Object.values(briefing?.macro_context ?? {});
  const portfolioImpact = Object.values(briefing?.portfolio_impact ?? {});
  const thesisUpdates = briefing?.thesis_updates?.updates ?? [];
  // F-001 (out-of-scope extra finding): GET /research/briefings/history
  // returns a bare list[MorningBriefingResponse], not a {briefings: [...]}
  // wrapper.
  const briefingHistory: MorningBriefingApi[] = Array.isArray(apiHistory) ? (apiHistory as MorningBriefingApi[]) : [];

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
        <span style={labelStyle}>{briefing?.briefing_date ?? '—'}</span>
        {briefing && (
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: briefing.ai_enabled ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)' }}>
            {briefing.ai_enabled ? 'AI-generated' : 'AI unavailable — assembled from raw data'}
          </span>
        )}
        <button className="btn-primary" onClick={handleGenerate} disabled={generating} style={{ marginLeft: briefing ? '8px' : 'auto' }}>
          {generating ? 'Generating…' : 'Generate Briefing'}
        </button>
      </div>

      {briefing?.executive_summary && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
          <h2 style={sectionTitle}>Executive Summary</h2>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.6, margin: 0 }}>{briefing.executive_summary}</p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {macroContext.length > 0 ? macroContext.map((m, i) => (
          <div key={i} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{m.name}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              {m.value.toFixed(2)}{m.yoy_change_pct != null ? ` (${m.yoy_change_pct >= 0 ? '+' : ''}${m.yoy_change_pct.toFixed(1)}% YoY)` : ''}
            </div>
          </div>
        )) : (
          <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
            <p style={labelStyle}>No macro context available for this briefing.</p>
          </div>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Thesis Updates</h2>
          {thesisUpdates.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {thesisUpdates.map((t, i) => (
                <div key={i} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{t.thesis_title ?? 'Untitled thesis'}</span>
                    {t.conviction_level && (
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-signal-neutral)' }}>{t.conviction_level}</span>
                    )}
                  </div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>v{t.version} &middot; updated {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : '—'}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={labelStyle}>No thesis updates in the last 7 days.</p>
          )}
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Portfolio Impact</h2>
          {portfolioImpact.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Entity', 'Impact'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Entity' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {portfolioImpact.map((p, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{p.entity_name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.price_change_1d_pct >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>
                    {p.price_change_1d_pct >= 0 ? '+' : ''}{p.price_change_1d_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          ) : (
            <p style={labelStyle}>No tracked-portfolio price moves for this briefing.</p>
          )}
        </div>
      </div>

      {/* Briefing History */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Briefing History</h2>
        {briefingHistory.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {briefingHistory.map((b) => (
              <div key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div>
                  <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 500 }}>{b.briefing_date}</span>
                  {b.executive_summary && (
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>{b.executive_summary}</span>
                  )}
                </div>
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
