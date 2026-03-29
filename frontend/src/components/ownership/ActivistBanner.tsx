import { useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ActivistInfo {
  name: string;
  position: string;
  filingDate: string;
  stake: number;
  intent: string;
}

export interface ActivistBannerProps {
  activist: ActivistInfo;
  onDismiss?: () => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ActivistBanner({ activist, onDismiss }: ActivistBannerProps) {
  const handleDismiss = useCallback(() => {
    onDismiss?.();
  }, [onDismiss]);

  return (
    <div
      style={{
        position: 'relative',
        background: 'rgba(224, 146, 58, 0.10)',
        border: '1px solid var(--color-signal-warning)',
        borderRadius: 4,
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
      }}
    >
      {/* Warning icon */}
      <span
        style={{
          fontSize: 16,
          lineHeight: 1,
          color: 'var(--color-signal-warning)',
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {'\u26A0'}
      </span>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title row */}
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-primary)',
            lineHeight: 1.4,
          }}
        >
          <span style={{ fontWeight: 700 }}>{activist.name}</span>
          {' — '}
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {activist.stake.toFixed(1)}% stake
          </span>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              color: 'var(--color-text-tertiary)',
              marginLeft: 8,
              fontSize: 'var(--text-xs)',
            }}
          >
            Filed {activist.filingDate}
          </span>
        </div>

        {/* Intent */}
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            marginTop: 4,
            lineHeight: 1.4,
          }}
        >
          <span
            style={{
              fontWeight: 600,
              color: 'var(--color-signal-warning)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginRight: 6,
            }}
          >
            {activist.position}
          </span>
          {activist.intent}
        </div>
      </div>

      {/* Dismiss button */}
      {onDismiss && (
        <button
          type="button"
          onClick={handleDismiss}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-text-tertiary)',
            cursor: 'pointer',
            fontSize: 16,
            lineHeight: 1,
            padding: 2,
            flexShrink: 0,
          }}
          title="Dismiss"
          aria-label="Dismiss activist alert"
        >
          {'\u2715'}
        </button>
      )}
    </div>
  );
}
