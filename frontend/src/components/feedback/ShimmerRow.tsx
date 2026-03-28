export interface ShimmerRowProps {
  /** Number of columns to shimmer */
  columns: number;
  /** Number of rows to render (default 5) */
  rows?: number;
}

/**
 * Skeleton loading rows for tables.
 * Animated shimmer gradient matching the terminal-panel background.
 */
export function ShimmerRow({ columns, rows = 5 }: ShimmerRowProps) {
  return (
    <>
      <style>{shimmerKeyframes}</style>
      {Array.from({ length: rows }, (_, rowIdx) => (
        <tr key={rowIdx}>
          {Array.from({ length: columns }, (_, colIdx) => (
            <td
              key={colIdx}
              style={{
                padding: 'var(--table-cell-py) var(--table-cell-px)',
                height: 'var(--table-row-height)',
                borderBottom: '1px solid var(--color-surface-border)',
              }}
            >
              <div
                style={{
                  height: '12px',
                  width: getColShimmerWidth(colIdx, columns),
                  borderRadius: 'var(--radius-sm)',
                  background: `linear-gradient(
                    90deg,
                    var(--color-surface-raised) 25%,
                    var(--color-surface-overlay) 50%,
                    var(--color-surface-raised) 75%
                  )`,
                  backgroundSize: '200% 100%',
                  animation: 'shimmer 1.5s ease-in-out infinite',
                  animationDelay: `${rowIdx * 80}ms`,
                }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/* ── Helpers ───────────────────────────────────────────────── */

const shimmerKeyframes = `
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
`;

/** First column wider, numeric columns narrower */
function getColShimmerWidth(colIdx: number, total: number): string {
  if (colIdx === 0) return '80%';
  if (colIdx >= total - 2) return '40%'; // last two cols narrow (numbers)
  return '60%';
}
