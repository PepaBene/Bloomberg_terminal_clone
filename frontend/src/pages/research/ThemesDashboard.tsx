// ---------------------------------------------------------------------------
// Themes Dashboard — Macro Themes with Sector Sensitivity Heatmap
// ---------------------------------------------------------------------------
import { useResearchThemes } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
function heatColor(v: number): string {
  if (v >= 2) return 'var(--color-signal-positive)';
  if (v >= 1) return '#1a8a5a';
  if (v > -1) return 'var(--color-text-tertiary)';
  if (v > -2) return '#c04545';
  return 'var(--color-signal-negative)';
}

// F-011: empty fallbacks. Default themes used to render specific tickers
// (NVDA/AVGO/AMD, AAPL/QCOM/INTC, etc.) and a hardcoded heatmap as if
// they were the user's research themes — they aren't.
const themes: { name: string; direction: string; conviction: number; tickers: string[]; horizon: string }[] = [];

const sectors = ['Tech', 'Health', 'Finance', 'ConDisc', 'Energy', 'Indust', 'Staples'];
const heatmapData: { theme: string; values: number[] }[] = [];

export default function ThemesDashboard() {
  const { data: apiThemes } = useResearchThemes() as { data: any };

  const activeThemes = (apiThemes as any)?.themes ?? themes;
  const activeHeatmap = (apiThemes as any)?.heatmap ?? heatmapData;
  const activeSectors = (apiThemes as any)?.sectors ?? sectors;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Macro Themes</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Thematic analysis with sector sensitivity and portfolio impact</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Active Themes */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Active Themes</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeThemes.map((t) => (
              <div key={t.name} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{t.name}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: t.direction === 'Bullish' ? 'var(--color-signal-positive)' : t.direction === 'Bearish' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{t.direction}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {t.tickers.map((tk) => (
                      <span key={tk} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', background: 'var(--color-surface-base)', padding: '1px 4px', borderRadius: '2px' }}>{tk}</span>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Conv: {t.conviction}/10</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{t.horizon}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sector Sensitivity Heatmap */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Sector Sensitivity Heatmap</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>Theme</th>
              {activeSectors.map((s) => (
                <th key={s} style={{ ...labelStyle, textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', fontSize: 'var(--text-xs)' }}>{s}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeHeatmap.map((row) => (
                <tr key={row.theme} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{row.theme}</td>
                  {row.values.map((v, i) => (
                    <td key={i} style={{ textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: heatColor(v) }}>
                        {v > 0 ? '+' : ''}{v}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '8px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>+3 Strong Positive</span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>0 Neutral</span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)' }}>-3 Strong Negative</span>
          </div>
        </div>
      </div>
    </div>
  );
}
