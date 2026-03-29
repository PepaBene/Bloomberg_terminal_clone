import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface IntelModule {
  name: string;
  score: number;
  classification: string;
}

export interface CompanyIntelCardProps {
  modules: IntelModule[];
  overallScore?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function qualityColor(score: number): string {
  if (score >= 80) return 'var(--color-quality-5)';
  if (score >= 60) return 'var(--color-quality-4)';
  if (score >= 40) return 'var(--color-quality-3)';
  if (score >= 20) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CompanyIntelCard({
  modules,
  overallScore,
  className,
}: CompanyIntelCardProps) {
  const computedOverall =
    overallScore ??
    (modules.length > 0
      ? Math.round(
          modules.reduce((sum, m) => sum + m.score, 0) / modules.length,
        )
      : 0);
  const overallColor = qualityColor(computedOverall);

  return (
    <div
      className={clsx('flex flex-col gap-3', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '16px',
      }}
    >
      {/* Overall score header */}
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
          {computedOverall}
        </span>
        <div className="flex flex-col">
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Company Intelligence
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            / 100
          </span>
        </div>
      </div>

      {/* Module rows */}
      <div className="flex flex-col gap-2">
        {modules.map((mod) => {
          const barColor = qualityColor(mod.score);
          const pct = Math.min(mod.score, 100);

          return (
            <div key={mod.name} className="flex flex-col gap-1">
              {/* Label + classification + score */}
              <div className="flex items-center justify-between gap-2">
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-primary)',
                    flex: 1,
                    minWidth: 0,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {mod.name}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    color: barColor,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '1px 6px',
                    border: `1px solid ${barColor}`,
                    borderRadius: '9999px',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}
                >
                  {mod.classification}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    color: barColor,
                    fontVariantNumeric: 'tabular-nums',
                    minWidth: 24,
                    textAlign: 'right',
                    flexShrink: 0,
                  }}
                >
                  {mod.score}
                </span>
              </div>

              {/* Progress bar */}
              <div
                style={{
                  height: 6,
                  borderRadius: 3,
                  background:
                    'var(--color-surface-overlay, rgba(255,255,255,0.06))',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: barColor,
                    borderRadius: 3,
                    transition: 'width var(--transition-normal, 0.2s)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
