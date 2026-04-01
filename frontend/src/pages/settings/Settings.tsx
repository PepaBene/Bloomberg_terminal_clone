// ---------------------------------------------------------------------------
// Settings — User Preferences, API Keys, Notifications, Theme
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const rowStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' };
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

const apiKeys = [
  { name: 'Bloomberg API', status: 'Connected', key: 'blp_****_7f2a' },
  { name: 'SEC EDGAR', status: 'Connected', key: 'edgar_****_9b1c' },
  { name: 'Federal Reserve (FRED)', status: 'Connected', key: 'fred_****_4d8e' },
  { name: 'Custom Data Source', status: 'Not Configured', key: '-' },
];

const THEME_OPTIONS = ['Dark (Default)', 'Light', 'System'] as const;

const THEME_CSS_MAP: Record<string, Record<string, string>> = {
  'Dark (Default)': { '--color-surface-base': '#0a0a0f', '--color-text-primary': '#e8e6e3' },
  'Light':          { '--color-surface-base': '#f5f5f5', '--color-text-primary': '#1a1a1a' },
  'System':         {},
};

export default function Settings() {
  const [activeTheme, setActiveTheme] = useState<string>('Dark (Default)');
  const [notifState, setNotifState] = useState(() =>
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
      Object.keys(THEME_CSS_MAP['Dark (Default)']).forEach((prop) => {
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
        </div>

        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>API Connections</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Data Source', 'Status', 'API Key'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {apiKeys.map((a) => (
                <tr key={a.name} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{a.name}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: a.status === 'Connected' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{a.status}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.key}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
