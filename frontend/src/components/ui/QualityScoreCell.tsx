export interface QualityScoreCellProps {
  /** Quality score value */
  score: number;
  /** Maximum score value (default 10) */
  max?: number;
  /** Optional display label like "Strong", "Weak" */
  label?: string;
}

/**
 * Quality score pill for table cells.
 * Maps score to quality-1 through quality-5 tier colors.
 */
export function QualityScoreCell({
  score,
  max = 10,
  label,
}: QualityScoreCellProps) {
  const tier = getQualityTier(score, max);
  const color = tierColors[tier];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--space-1)',
        padding: '1px 8px',
        borderRadius: '9999px',
        background: `${color}26`, // ~15% opacity hex
        color: color,
        fontFamily: 'var(--font-data)',
        fontSize: 'var(--text-sm)',
        fontWeight: 500,
        fontVariantNumeric: 'tabular-nums',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      {formatScore(score, max)}
      {label && (
        <span style={{ fontSize: 'var(--text-xs)', opacity: 0.85 }}>
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

function getQualityTier(score: number, max: number): Tier {
  const pct = Math.max(0, Math.min(1, score / max));
  if (pct >= 0.8) return 5;
  if (pct >= 0.6) return 4;
  if (pct >= 0.4) return 3;
  if (pct >= 0.2) return 2;
  return 1;
}

function formatScore(score: number, max: number): string {
  // Display as-is for whole numbers, one decimal otherwise
  const display = Number.isInteger(score) ? String(score) : score.toFixed(1);
  return `${display}/${max}`;
}
