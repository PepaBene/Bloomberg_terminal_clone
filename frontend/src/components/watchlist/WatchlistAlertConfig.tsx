import { useState } from 'react';
import type { CSSProperties, ChangeEvent } from 'react';
import { api } from '@/api/client';

export interface WatchlistAlertConfigProps {
  watchlistId: string;
  entityId?: string;
}

type PriceDirection = 'above' | 'below';

interface AlertConfig {
  priceTargetEnabled: boolean;
  priceTargetDirection: PriceDirection;
  priceTarget: string;
  pctChangeEnabled: boolean;
  pctChangeThreshold: string;
  earningsEnabled: boolean;
  newsKeywordsEnabled: boolean;
  newsKeywords: string;
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  const trackStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    width: '32px',
    height: '16px',
    background: checked ? 'var(--color-accent-primary)' : 'var(--color-surface-border)',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'background 0.15s',
    flexShrink: 0,
    position: 'relative',
  };

  const thumbStyle: CSSProperties = {
    position: 'absolute',
    left: checked ? '18px' : '2px',
    top: '2px',
    width: '12px',
    height: '12px',
    background: 'var(--color-text-primary)',
    borderRadius: '50%',
    transition: 'left 0.15s',
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
      <div
        role="switch"
        aria-checked={checked}
        style={trackStyle}
        onClick={() => onChange(!checked)}
      >
        <div style={thumbStyle} />
      </div>
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: checked ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
          transition: 'color 0.15s',
        }}
      >
        {label}
      </span>
    </div>
  );
}

export function WatchlistAlertConfig({ watchlistId, entityId }: WatchlistAlertConfigProps) {
  const [config, setConfig] = useState<AlertConfig>({
    priceTargetEnabled: false,
    priceTargetDirection: 'above',
    priceTarget: '',
    pctChangeEnabled: false,
    pctChangeThreshold: '5',
    earningsEnabled: false,
    newsKeywordsEnabled: false,
    newsKeywords: '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = <K extends keyof AlertConfig>(key: K, value: AlertConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    const endpoint = entityId
      ? `/v3/portfolios/watchlists/${watchlistId}/entities/${entityId}/alerts`
      : `/v3/portfolios/watchlists/${watchlistId}/alerts`;
    try {
      await api.post(endpoint, config);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-4)',
  };

  const sectionStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    padding: 'var(--space-3)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
  };

  const inputStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontSize: 'var(--text-sm)',
    fontVariantNumeric: 'tabular-nums',
    color: 'var(--color-text-primary)',
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    padding: '4px 8px',
    height: '28px',
    outline: 'none',
    width: '120px',
  };

  const selectStyle: CSSProperties = {
    ...inputStyle,
    width: '90px',
  };

  return (
    <div className="animate-in" style={rootStyle}>
      {/* Price Target */}
      <div style={sectionStyle}>
        <Toggle
          checked={config.priceTargetEnabled}
          onChange={(v) => update('priceTargetEnabled', v)}
          label="Price Target Alert"
        />
        {config.priceTargetEnabled && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              Trigger when price goes
            </span>
            <select
              style={selectStyle}
              value={config.priceTargetDirection}
              onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                update('priceTargetDirection', e.target.value as PriceDirection)
              }
            >
              <option value="above">above</option>
              <option value="below">below</option>
            </select>
            <input
              type="number"
              style={inputStyle}
              value={config.priceTarget}
              onChange={(e) => update('priceTarget', e.target.value)}
              placeholder="Price"
              min="0"
              step="any"
            />
          </div>
        )}
      </div>

      {/* % Change */}
      <div style={sectionStyle}>
        <Toggle
          checked={config.pctChangeEnabled}
          onChange={(v) => update('pctChangeEnabled', v)}
          label="% Change Threshold"
        />
        {config.pctChangeEnabled && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              Alert when daily change exceeds
            </span>
            <input
              type="number"
              style={{ ...inputStyle, width: '70px' }}
              value={config.pctChangeThreshold}
              onChange={(e) => update('pctChangeThreshold', e.target.value)}
              min="0.1"
              step="0.1"
            />
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>%</span>
          </div>
        )}
      </div>

      {/* Earnings Events */}
      <div style={sectionStyle}>
        <Toggle
          checked={config.earningsEnabled}
          onChange={(v) => update('earningsEnabled', v)}
          label="Earnings Event Alerts"
        />
      </div>

      {/* News Keywords */}
      <div style={sectionStyle}>
        <Toggle
          checked={config.newsKeywordsEnabled}
          onChange={(v) => update('newsKeywordsEnabled', v)}
          label="News Keyword Alerts"
        />
        {config.newsKeywordsEnabled && (
          <div style={{ marginTop: 'var(--space-1)' }}>
            <input
              type="text"
              style={{ ...inputStyle, width: '100%' }}
              value={config.newsKeywords}
              onChange={(e) => update('newsKeywords', e.target.value)}
              placeholder="e.g. merger, lawsuit, guidance (comma-separated)"
            />
          </div>
        )}
      </div>

      {error && (
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)' }}>
          {error}
        </span>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            padding: '6px 20px',
            background: saved ? 'var(--color-signal-positive)' : 'var(--color-accent-primary)',
            color: 'var(--color-surface-void)',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: saving ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.6 : 1,
            transition: 'background 0.2s',
          }}
        >
          {saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Alerts'}
        </button>
      </div>
    </div>
  );
}

export default WatchlistAlertConfig;
