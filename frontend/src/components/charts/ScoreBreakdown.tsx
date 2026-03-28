import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ScoreItem {
  name: string;
  score: number;
  max: number;
  description?: string;
}

export interface ScoreBreakdownProps {
  scores: ScoreItem[];
  title: string;
  overallScore: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function qualityColor(pct: number): string {
  if (pct >= 80) return 'var(--color-quality-5)';
  if (pct >= 60) return 'var(--color-quality-4)';
  if (pct >= 40) return 'var(--color-quality-3)';
  if (pct >= 20) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

function qualityLabel(pct: number): string {
  if (pct >= 80) return 'Excellent';
  if (pct >= 60) return 'Good';
  if (pct >= 40) return 'Moderate';
  if (pct >= 20) return 'Weak';
  return 'Poor';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ScoreBreakdown({
  scores,
  title,
  overallScore,
  className,
}: ScoreBreakdownProps) {
  const overallMax = scores.length > 0
    ? scores.reduce((s, item) => s + item.max, 0)
    : 100;
  const overallPct = overallMax > 0 ? (overallScore / overallMax) * 100 : 0;
  const overallColor = qualityColor(overallPct);

  return (
    <div className={clsx('terminal-panel flex flex-col gap-3', className)}>
      <h3 className="terminal-section-title">{title}</h3>

      {/* Overall score hero */}
      <div className="flex items-center gap-3">
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-3xl)',
            fontWeight: 600,
            color: overallColor,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1,
          }}
        >
          {overallScore}
        </span>
        <div className="flex flex-col">
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-secondary)',
            }}
          >
            / {overallMax}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: overallColor,
              fontWeight: 500,
            }}
          >
            {qualityLabel(overallPct)}
          </span>
        </div>
      </div>

      {/* Sub-score progress bars */}
      <div className="flex flex-col gap-2">
        {scores.map((item) => {
          const pct = item.max > 0 ? (item.score / item.max) * 100 : 0;
          const barColor = qualityColor(pct);

          return (
            <div key={item.name} className="flex flex-col gap-0.5">
              {/* Label row */}
              <div className="flex items-baseline justify-between">
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-primary)',
                  }}
                  title={item.description}
                >
                  {item.name}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    color: barColor,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {item.score}/{item.max}
                </span>
              </div>

              {/* Progress bar */}
              <div
                style={{
                  height: 6,
                  borderRadius: 3,
                  background: 'var(--color-surface-overlay)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(pct, 100)}%`,
                    background: barColor,
                    borderRadius: 3,
                    transition: 'width var(--transition-normal)',
                  }}
                />
              </div>

              {/* Description */}
              {item.description && (
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: '9px',
                    color: 'var(--color-text-tertiary)',
                    lineHeight: 1.3,
                  }}
                >
                  {item.description}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
