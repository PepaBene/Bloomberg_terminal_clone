import type { CSSProperties } from 'react';

export interface PanelProgressProps {
  /** Optional label displayed above the bar */
  label?: string;
  /** 0-100 for determinate, or undefined for indeterminate (sliding) */
  progress?: number;
  /** Whether to show the loading bar at all (e.g. tie to a loading boolean) */
  loading?: boolean;
  /**
   * Whether to dim the panel content below with a centred status overlay.
   * The parent component MUST have `position: relative` for this to work.
   * Default false — just shows the top bar.
   */
  dimContent?: boolean;
  /** Status message to show in the dimmed overlay (e.g. "Running DCF…") */
  statusMessage?: string;
  /** Elapsed seconds to show alongside status (e.g. 2.3) */
  elapsedSeconds?: number;
}

/* ── Keyframe styles ──────────────────────────────────────────────── */

const indeterminateKeyframes = `
@keyframes progressSlide {
  0% { left: -40%; }
  100% { left: 100%; }
}
`;

const spinKeyframes = `
@keyframes spin {
  to { transform: rotate(360deg); }
}
`;

/* ── Overlay styles ───────────────────────────────────────────────── */

const overlayStyle: CSSProperties = {
  position: 'absolute',
  inset: 0,
  zIndex: 100,
  background: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexDirection: 'column',
  gap: 'var(--space-2)',
  backdropFilter: 'blur(1px)',
};

const spinnerStyle: CSSProperties = {
  width: 24,
  height: 24,
  border: '2px solid var(--color-surface-border)',
  borderTop: '2px solid var(--color-accent-primary)',
  borderRadius: '50%',
  animation: 'spin 0.8s linear infinite',
};

const statusTextStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const elapsedTextStyle: CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-xs)',
  color: 'var(--color-text-tertiary)',
  fontVariantNumeric: 'tabular-nums' as const,
};

/**
 * Thin progress bar rendered at the top of a panel.
 * Indeterminate mode shows a sliding animation; determinate shows a filled bar.
 *
 * When `dimContent` is true, also renders a full-panel dim overlay with a
 * spinning loader and optional status/elapsed text. The parent MUST have
 * `position: relative`.
 */
export function PanelProgress({
  label,
  progress,
  loading,
  dimContent = false,
  statusMessage,
  elapsedSeconds,
}: PanelProgressProps) {
  const isDeterminate = progress !== undefined;
  const clampedPct = isDeterminate ? Math.max(0, Math.min(100, progress)) : 0;

  // Show the top bar when loading is explicitly true, or when progress is provided
  const showBar = loading !== false && (loading === true || isDeterminate || (!dimContent));

  return (
    <>
      {/* Dim overlay */}
      {dimContent && (
        <>
          <style>{spinKeyframes}</style>
          <div style={overlayStyle}>
            <div style={spinnerStyle} />
            {statusMessage && (
              <span style={statusTextStyle}>{statusMessage}</span>
            )}
            {elapsedSeconds !== undefined && (
              <span style={elapsedTextStyle}>{elapsedSeconds.toFixed(1)}s</span>
            )}
          </div>
        </>
      )}

      {/* Top progress bar */}
      {showBar && (
        <div style={{ width: '100%' }}>
          {/* Label + percentage */}
          {(label || isDeterminate) && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 'var(--space-1)',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {label && <span>{label}</span>}
              {isDeterminate && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums' as const,
                  }}
                >
                  {Math.round(clampedPct)}%
                </span>
              )}
            </div>
          )}

          {/* Track */}
          <div
            style={{
              width: '100%',
              height: '3px',
              borderRadius: '2px',
              background: 'var(--color-surface-border)',
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            {isDeterminate ? (
              /* Determinate bar */
              <div
                style={{
                  height: '100%',
                  width: `${clampedPct}%`,
                  background: 'var(--color-accent-primary)',
                  borderRadius: '2px',
                  transition: 'width var(--transition-normal)',
                }}
              />
            ) : (
              /* Indeterminate sliding bar */
              <>
                <style>{indeterminateKeyframes}</style>
                <div
                  style={{
                    position: 'absolute',
                    height: '100%',
                    width: '40%',
                    background: 'var(--color-accent-primary)',
                    borderRadius: '2px',
                    animation: 'progressSlide 1.4s ease-in-out infinite',
                  }}
                />
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
