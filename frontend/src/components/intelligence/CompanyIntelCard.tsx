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
  if (score >= 80) return 'var(--quality-5)';
  if (score >= 60) return 'var(--quality-4)';
  if (score >= 40) return 'var(--quality-3)';
  if (score >= 20) return 'var(--quality-2)';
  return 'var(--quality-1)';
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
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-4)',
      }}
    >
      {/* Overall score header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            color: overallColor,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1,
          }}
        >
          {computedOverall}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--text-secondary)',
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
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--text-tertiary)',
            }}
          >
            / 100
          </span>
        </div>
      </div>

      {/* Module rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        {modules.map((mod) => {
          const barColor = qualityColor(mod.score);
          const pct = Math.min(mod.score, 100);

          return (
            <div
              key={mod.name}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                transition: 'background var(--transition-fast)',
                cursor: 'default',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--surface-overlay)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {/* Label + classification + score */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--text-primary)',
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
                    fontVariantNumeric: 'tabular-nums',
                    color: barColor,
                    background: `color-mix(in srgb, ${barColor} 15%, transparent)`,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '1px var(--space-1)',
                    borderRadius: 'var(--radius-sm)',
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
                    fontVariantNumeric: 'tabular-nums',
                    color: barColor,
                    minWidth: 24,
                    textAlign: 'right',
                    flexShrink: 0,
                  }}
                >
                  {mod.score}
                </span>
              </div>

              {/* Progress bar with quality-tier gradient */}
              <div
                style={{
                  height: 6,
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--surface-overlay)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: barColor,
                    borderRadius: 'var(--radius-sm)',
                    transition: 'width var(--transition-normal)',
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
