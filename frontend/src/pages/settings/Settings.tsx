// ---------------------------------------------------------------------------
// Settings — User Preferences, Data Connections, Notifications, Theme
//
// Honesty pass (DATA_WIRING_AUDIT §8.1): there is no user-profile / api-key
// backend (auth is JWT-only: register/token/me). The previous version POSTed to
// nonexistent /v1/auth/profile + /v1/auth/api-keys and rendered fabricated
// masked API keys with a fake "Connected" status. Those are removed:
//   - Display prefs, theme and notification toggles are now honestly LOCAL
//     (session-scoped UI state), not pretend-persisted to a missing endpoint.
//   - The Data Connections panel documents how each source is configured
//     (server-side env vars) instead of showing invented keys/status.
//   - Custom Classifications is wired to the REAL GET /v1/classifications
//     (custom_classifications.py) with an honest empty state.
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useCustomClassifications } from '@/hooks';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };
const rowStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' };
const noteStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', margin: '10px 0 0 0' };

const preferences = [
  { label: 'Default Date Range', value: '1Y' },
  { label: 'Compact Mode', value: 'Off' },
  { label: 'Table Density', value: 'Normal' },
  { label: 'Number Format', value: 'US (1,234.56)' },
  { label: 'Time Zone', value: 'America/New_York' },
];

const notifications = [
  { label: 'Price Alerts', enabled: true },
  { label: 'Earnings Alerts', enabled: true },
  { label: 'Credit Alerts', enabled: true },
  { label: 'Filing Alerts', enabled: false },
  { label: 'Macro Event Alerts', enabled: true },
  { label: 'Email Digest', enabled: false },
];

// Data sources are configured server-side via environment variables (see
// CONNECTING_TO_REAL_DATA.md / .env.example). There is no API-key management
// endpoint, so we describe the configuration mechanism rather than invent keys.
const dataSources = [
  { name: 'SEC EDGAR', envVar: 'EDGAR_USER_AGENT', note: 'Filings, fundamentals, ownership' },
  { name: 'Federal Reserve (FRED)', envVar: 'FRED_API_KEY', note: 'Macro indicators, yield curve, spreads' },
  { name: 'Polygon.io', envVar: 'POLYGON_API_KEY', note: 'End-of-day equity prices' },
  { name: 'OpenFIGI', envVar: 'OPENFIGI_API_KEY', note: 'Security master / identifiers' },
  { name: 'Finnhub', envVar: 'FINNHUB_API_KEY', note: 'News, earnings actuals' },
  { name: 'Anthropic (Claude)', envVar: 'ANTHROPIC_API_KEY', note: 'AI narratives / research' },
];

const THEME_OPTIONS = ['Dark (Default)', 'Light', 'System'] as const;

const THEME_CSS_MAP: Record<string, Record<string, string>> = {
  'Dark (Default)': { '--color-surface-base': '#0a0a0f', '--color-text-primary': '#e8e6e3' },
  'Light':          { '--color-surface-base': '#f5f5f5', '--color-text-primary': '#1a1a1a' },
  'System':         {},
};

interface ClassificationDTO {
  classification_id: string;
  name: string;
  description?: string | null;
  members?: unknown[];
}

export default function Settings() {
  const { data: apiClassifications, isLoading: loadingClassifications } =
    useCustomClassifications() as { data: { data?: ClassificationDTO[] } | undefined; isLoading: boolean };
  const classifications: ClassificationDTO[] = apiClassifications?.data ?? [];

  const [activeTheme, setActiveTheme] = useState<string>('Dark (Default)');
  const [notifState, setNotifState] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(notifications.map((n) => [n.label, n.enabled])),
  );

  const handleThemeChange = useCallback((theme: string) => {
    setActiveTheme(theme);
    const vars = THEME_CSS_MAP[theme];
    if (vars && Object.keys(vars).length > 0) {
      Object.entries(vars).forEach(([prop, val]) => {
        document.documentElement.style.setProperty(prop, val);
      });
    } else {
      // System: remove overrides so OS preference applies
      Object.keys(THEME_CSS_MAP['Dark (Default)'] ?? {}).forEach((prop) => {
        document.documentElement.style.removeProperty(prop);
      });
    }
  }, []);

  const toggleNotification = useCallback((label: string) => {
    setNotifState((prev) => ({ ...prev, [label]: !prev[label] }));
  }, []);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Settings</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>User preferences, data connections, and notification configuration</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Display Preferences</h2>
          {preferences.map((p) => (
            <div key={p.label} style={rowStyle}>
              <span style={labelStyle}>{p.label}</span>
              <span style={{ ...dataStyle, fontSize: 'var(--text-sm)' }}>{p.value}</span>
            </div>
          ))}
          <div style={{ marginTop: '12px' }}>
            <h2 style={sectionTitle}>Theme</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              {THEME_OPTIONS.map((t) => (
                <span
                  key={t}
                  onClick={() => handleThemeChange(t)}
                  style={{
                    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '4px 12px', borderRadius: '3px',
                    background: t === activeTheme ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
                    color: t === activeTheme ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
                    cursor: 'pointer',
                  }}
                >{t}</span>
              ))}
            </div>
          </div>
          <p style={noteStyle}>Display preferences and theme apply to the current session (no server-side profile store).</p>
        </div>

        <div style={panelStyle}>
          <h2 style={sectionTitle}>Notifications</h2>
          {notifications.map((n) => (
            <div key={n.label} style={rowStyle}>
              <span style={labelStyle}>{n.label}</span>
              <span
                onClick={() => toggleNotification(n.label)}
                style={{
                  fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 500,
                  color: notifState[n.label] ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                {notifState[n.label] ? 'ON' : 'OFF'}
              </span>
            </div>
          ))}
          <p style={noteStyle}>Toggles are session-local; alert delivery is driven by backend alert rules.</p>
        </div>

        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Data Connections</h2>
          <p style={{ ...labelStyle, marginBottom: '12px' }}>
            External data sources are configured server-side via environment variables.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Data Source', 'Environment Variable', 'Used For'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {dataSources.map((s) => (
                <tr key={s.name} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.name}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.envVar}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Custom Classifications</h2>
          <p style={{ ...labelStyle, marginBottom: '12px' }}>Custom entity groupings and categories</p>
          {loadingClassifications ? (
            <p style={labelStyle}>Loading…</p>
          ) : classifications.length === 0 ? (
            <p style={labelStyle}>No custom classifications yet.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                {['Name', 'Description', 'Entities'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {classifications.map((c) => (
                  <tr key={c.classification_id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{c.name}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.description ?? '—'}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.members?.length ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
