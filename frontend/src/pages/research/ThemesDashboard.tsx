// ---------------------------------------------------------------------------
// Themes Dashboard — Macro Theme Exposure Scores
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useResearchThemes } from '@/hooks';
import { useThemeDetail, useThemeSecurities } from '@/api/hooks/useResearch';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

function directionColor(direction: string | null | undefined): string {
  const d = (direction ?? '').toUpperCase();
  if (d.includes('POS') || d.includes('BULL')) return 'var(--color-signal-positive)';
  if (d.includes('NEG') || d.includes('BEAR')) return 'var(--color-signal-negative)';
  return 'var(--color-signal-warning)';
}

interface ThemeScoreRow {
  id: string;
  entity_id: string;
  theme: string;
  exposure_score: number | null;
  sensitivity_direction: string | null;
  quantified_exposure: string | null;
  as_of_date: string;
}

interface ThemeSummary {
  theme: string;
  entityCount: number;
  avgExposure: number | null;
  latestAsOf: string;
}

// The real endpoint (/v4/research/themes/dashboard) returns a bare array of
// per-entity exposure scores keyed by theme label — not a pre-grouped
// {themes, heatmap, sectors} shape. Group it client-side into one card per
// theme label rather than accessing nonexistent `.themes`/`.heatmap`
// properties on that array (the bug this page previously had).
function groupByTheme(rows: ThemeScoreRow[]): ThemeSummary[] {
  const groups = new Map<string, ThemeScoreRow[]>();
  for (const r of rows) {
    const list = groups.get(r.theme) ?? [];
    list.push(r);
    groups.set(r.theme, list);
  }
  return Array.from(groups.entries())
    .map(([theme, items]) => {
      const scores = items.map((i) => i.exposure_score).filter((v): v is number => v != null);
      const avgExposure = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
      const latestAsOf = items.map((i) => i.as_of_date).sort().slice(-1)[0];
      return { theme, entityCount: items.length, avgExposure, latestAsOf };
    })
    .sort((a, b) => (b.avgExposure ?? -Infinity) - (a.avgExposure ?? -Infinity));
}

export default function ThemesDashboard() {
  const { data: apiThemes, isLoading, isError } = useResearchThemes();
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);

  const rows: ThemeScoreRow[] = Array.isArray(apiThemes) ? (apiThemes as ThemeScoreRow[]) : [];
  const summaries = groupByTheme(rows);

  const { data: detail } = useThemeDetail(selectedTheme ?? '', { enabled: !!selectedTheme });
  const { data: securitiesRaw } = useThemeSecurities(selectedTheme ?? '', { enabled: !!selectedTheme });
  const securities = Array.isArray(securitiesRaw) ? (securitiesRaw as any[]) : [];
  const themeDetail = detail as
    | { entity_count: number; avg_exposure_score: number | null; bullish_count: number; bearish_count: number; neutral_count: number; latest_as_of_date: string | null }
    | undefined;

  if (isLoading) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Macro Themes</h1>
      <p style={{ ...labelStyle, marginTop: '12px' }}>Loading themes data...</p>
    </div>
  );

  if (isError) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Macro Themes</h1>
      <p style={{ ...labelStyle, marginTop: '12px', color: 'var(--color-signal-negative)' }}>Failed to load themes data.</p>
    </div>
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Macro Themes</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Entity exposure scores by macro theme — click a theme to see its most-exposed securities</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Active Themes */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Active Themes</h2>
          {summaries.length === 0 ? (
            <p style={labelStyle}>No macro theme exposure scores computed yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {summaries.map((t) => (
                <div
                  key={t.theme}
                  onClick={() => setSelectedTheme(t.theme)}
                  style={{
                    padding: '8px',
                    background: t.theme === selectedTheme ? 'var(--color-accent-primary-muted, var(--color-surface-overlay))' : 'var(--color-surface-overlay)',
                    border: t.theme === selectedTheme ? '1px solid var(--color-accent-primary)' : '1px solid transparent',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{t.theme}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: t.avgExposure != null ? heatColor(t.avgExposure) : 'var(--color-text-tertiary)' }}>
                      {t.avgExposure != null ? `${t.avgExposure > 0 ? '+' : ''}${t.avgExposure.toFixed(1)}` : '—'}
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
                    {t.entityCount} {t.entityCount === 1 ? 'entity' : 'entities'} scored · as of {t.latestAsOf}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Theme Detail */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>{selectedTheme ? `Theme Detail: ${selectedTheme}` : 'Theme Detail'}</h2>
          {!selectedTheme ? (
            <p style={labelStyle}>Select a theme on the left to see its exposure summary and most-exposed securities.</p>
          ) : (
            <>
              {themeDetail && (
                <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  <span style={labelStyle}>Entities: <strong style={{ color: 'var(--color-text-primary)' }}>{themeDetail.entity_count}</strong></span>
                  <span style={labelStyle}>Avg exposure: <strong style={{ color: 'var(--color-text-primary)' }}>{themeDetail.avg_exposure_score ?? '—'}</strong></span>
                  <span style={{ ...labelStyle, color: 'var(--color-signal-positive)' }}>Bullish: {themeDetail.bullish_count}</span>
                  <span style={{ ...labelStyle, color: 'var(--color-signal-negative)' }}>Bearish: {themeDetail.bearish_count}</span>
                  <span style={labelStyle}>Neutral: {themeDetail.neutral_count}</span>
                </div>
              )}
              {securities.length === 0 ? (
                <p style={labelStyle}>No scored securities for this theme yet.</p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Entity</th>
                    <th style={{ ...labelStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Exposure</th>
                    <th style={{ ...labelStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Direction</th>
                  </tr></thead>
                  <tbody>
                    {securities.map((s) => (
                      <tr key={s.entity_id} style={{ height: 'var(--table-row-height)' }}>
                        <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.entity_name ?? s.entity_id}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.exposure_score ?? '—'}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: directionColor(s.sensitivity_direction), padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sensitivity_direction ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function heatColor(v: number): string {
  if (v >= 2) return 'var(--color-signal-positive)';
  if (v >= 1) return '#1a8a5a';
  if (v > -1) return 'var(--color-text-tertiary)';
  if (v > -2) return '#c04545';
  return 'var(--color-signal-negative)';
}
