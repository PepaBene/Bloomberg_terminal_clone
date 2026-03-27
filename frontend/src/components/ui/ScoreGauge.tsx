import clsx from 'clsx';

export interface ScoreGaugeProps {
  /** Numeric score (0-100) */
  score: number;
  /** Label shown below the gauge */
  label?: string;
  /** Additional CSS class */
  className?: string;
}

/* Map a 0-100 score to a 1-5 quality tier */
function scoreTier(score: number): 1 | 2 | 3 | 4 | 5 {
  if (score >= 90) return 5;
  if (score >= 75) return 4;
  if (score >= 55) return 3;
  if (score >= 35) return 2;
  return 1;
}

const TIER_LABELS: Record<number, string> = {
  5: 'Excellent',
  4: 'Good',
  3: 'Average',
  2: 'Below',
  1: 'Poor',
};

const TIER_COLORS: Record<number, string> = {
  5: 'var(--color-quality-5)',
  4: 'var(--color-quality-4)',
  3: 'var(--color-quality-3)',
  2: 'var(--color-quality-2)',
  1: 'var(--color-quality-1)',
};

export function ScoreGauge({ score, label, className }: ScoreGaugeProps) {
  const tier = scoreTier(score);
  const tierColor = TIER_COLORS[tier];
  const tierLabel = TIER_LABELS[tier];

  // SVG circular gauge parameters
  const size = 80;
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedScore = Math.max(0, Math.min(100, score));
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div
      className={clsx(
        'inline-flex flex-col items-center gap-1',
        className,
      )}
    >
      {/* Circular gauge */}
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="block"
        >
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--color-surface-border)"
            strokeWidth={strokeWidth}
          />
          {/* Filled arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={tierColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: 'stroke-dashoffset 0.4s ease' }}
          />
        </svg>

        {/* Center text */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center"
          style={{ pointerEvents: 'none' }}
        >
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-md)',
              fontWeight: 600,
              color: tierColor,
              lineHeight: '1',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {score}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: '8px',
              color: 'var(--color-text-tertiary)',
              lineHeight: '1',
            }}
          >
            /100
          </span>
        </div>
      </div>

      {/* Tier badge */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: tierColor,
          fontWeight: 500,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        {tierLabel}
      </span>

      {/* 5-segment bar */}
      <div className="flex gap-[2px]">
        {([1, 2, 3, 4, 5] as const).map((t) => (
          <div
            key={t}
            style={{
              width: '10px',
              height: '3px',
              borderRadius: '1px',
              background:
                t <= tier ? TIER_COLORS[t] : 'var(--color-surface-border)',
              transition: 'background 0.3s',
            }}
          />
        ))}
      </div>

      {/* Label */}
      {label && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            lineHeight: '1.2',
            marginTop: '2px',
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
