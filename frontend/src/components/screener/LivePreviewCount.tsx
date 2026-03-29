/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface LivePreviewCountProps {
  count: number | null;
  loading?: boolean;
  total?: number;
}

/* ------------------------------------------------------------------ */
/*  Shimmer keyframes (inline style tag)                               */
/* ------------------------------------------------------------------ */

const shimmerKeyframes = `
@keyframes screener-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
`;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function LivePreviewCount({ count, loading, total }: LivePreviewCountProps) {
  return (
    <>
      <style>{shimmerKeyframes}</style>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          background: 'var(--color-surface-raised)',
          borderRadius: 4,
          border: '1px solid var(--color-surface-border)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-secondary)',
          minHeight: 36,
        }}
      >
        {loading ? (
          /* Shimmer placeholder */
          <span
            style={{
              display: 'inline-block',
              width: 160,
              height: 14,
              borderRadius: 3,
              background:
                'linear-gradient(90deg, var(--color-surface-border) 25%, var(--color-surface-border-strong) 50%, var(--color-surface-border) 75%)',
              backgroundSize: '200% 100%',
              animation: 'screener-shimmer 1.5s ease-in-out infinite',
            }}
          />
        ) : count != null ? (
          <>
            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-lg)',
                fontWeight: 600,
                color: 'var(--color-accent-primary)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {count.toLocaleString()}
            </span>
            {total != null ? (
              <span>
                of{' '}
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {total.toLocaleString()}
                </span>{' '}
                companies match
              </span>
            ) : (
              <span>companies match</span>
            )}
          </>
        ) : (
          <span style={{ color: 'var(--color-text-tertiary)' }}>
            Add filters to begin screening
          </span>
        )}
      </div>
    </>
  );
}
