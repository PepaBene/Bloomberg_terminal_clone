export interface QualityScoreCellProps {
  /** Quality score value */
  score: number;
  /** Maximum score value (default 100) */
  max?: number;
  /** Optional display label like "Strong", "Weak" */
  label?: string;
}

const TOTAL_BLOCKS = 5;

/**
 * Quality score rendered as block bars for table cells.
 *
 * 5 blocks total, each 4px wide x 12px tall, 1px gap.
 * Filled blocks = Math.round(score / max * 5).
 * Filled blocks use the quality-tier color; empty blocks use the same
 * color at 15% opacity.
 *
 * Example:  ████░ 82   (4 filled green + 1 empty)
 */
export function QualityScoreCell({
  score,
  max = 100,
  label,
}: QualityScoreCellProps) {
  const pct = Math.max(0, Math.min(1, score / max));
  const filledCount = Math.round(pct * TOTAL_BLOCKS);
  const tier = getQualityTier(pct);
  const color = tierColors[tier];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        fontFamily: 'var(--font-data)',
        fontSize: 'var(--text-sm)',
        fontVariantNumeric: 'tabular-nums',
        lineHeight: 1,
        whiteSpace: 'nowrap',
      }}
    >
      {/* Block bar */}
      <span
        className="quality-bar"
        style={{ display: 'inline-flex', gap: '1px', verticalAlign: 'middle' }}
      >
        {Array.from({ length: TOTAL_BLOCKS }, (_, i) => {
          const filled = i < filledCount;
          return (
            <span
              key={i}
              className={`block ${filled ? 'filled' : 'empty'}`}
              style={{
                width: '4px',
                height: '12px',
                borderRadius: '1px',
                backgroundColor: color,
                opacity: filled ? 1 : 0.15,
              }}
            />
          );
        })}
      </span>

      {/* Numeric value */}
      <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
        {formatScore(score, max)}
      </span>

      {label && (
        <span
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {label}
        </span>
      )}
    </span>
  );
}

/* ── Helpers ───────────────────────────────────────────────── */

type Tier = 1 | 2 | 3 | 4 | 5;

const tierColors: Record<Tier, string> = {
  1: 'var(--color-quality-1)',
  2: 'var(--color-quality-2)',
  3: 'var(--color-quality-3)',
  4: 'var(--color-quality-4)',
  5: 'var(--color-quality-5)',
};

function getQualityTier(pct: number): Tier {
  if (pct >= 0.8) return 5;
  if (pct >= 0.6) return 4;
  if (pct >= 0.4) return 3;
  if (pct >= 0.2) return 2;
  return 1;
}

function formatScore(score: number, max: number): string {
  if (max === 100) {
    // For 0-100 scale, show just the integer
    return String(Math.round(score));
  }
  // Display as-is for whole numbers, one decimal otherwise
  const display = Number.isInteger(score) ? String(score) : score.toFixed(1);
  return `${display}/${max}`;
}
