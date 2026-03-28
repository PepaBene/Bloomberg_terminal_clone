export interface PanelProgressProps {
  /** Optional label displayed above the bar */
  label?: string;
  /** 0-100 for determinate, or undefined for indeterminate (sliding) */
  progress?: number;
}

/**
 * Thin progress bar rendered at the top of a panel.
 * Indeterminate mode shows a sliding animation; determinate shows a filled bar.
 */
export function PanelProgress({ label, progress }: PanelProgressProps) {
  const isDeterminate = progress !== undefined;
  const clampedPct = isDeterminate ? Math.max(0, Math.min(100, progress)) : 0;

  return (
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
                fontVariantNumeric: 'tabular-nums',
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
  );
}

/* ── Animation ────────────────────────────────────────────── */

const indeterminateKeyframes = `
@keyframes progressSlide {
  0% { left: -40%; }
  100% { left: 100%; }
}
`;
