import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MetricItem {
  label: string;
  value: string;
  change?: number;
  subValue?: string;
}

export interface KeyMetricsGridProps {
  metrics: MetricItem[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function changeDirection(change: number): 'positive' | 'negative' | 'neutral' {
  if (change > 0) return 'positive';
  if (change < 0) return 'negative';
  return 'neutral';
}

function changeColor(dir: 'positive' | 'negative' | 'neutral'): string {
  if (dir === 'positive') return 'var(--color-signal-positive)';
  if (dir === 'negative') return 'var(--color-signal-negative)';
  return 'var(--color-signal-neutral)';
}

function changeArrow(dir: 'positive' | 'negative' | 'neutral'): string {
  if (dir === 'positive') return '\u25B2';
  if (dir === 'negative') return '\u25BC';
  return '';
}

function formatChange(value: number): string {
  const abs = Math.abs(value);
  const sign = value > 0 ? '+' : '';
  return `${sign}${abs.toFixed(1)}%`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function KeyMetricsGrid({ metrics, className }: KeyMetricsGridProps) {
  return (
    <div
      className={clsx(
        'grid grid-cols-2 md:grid-cols-4 gap-[var(--panel-gap)]',
        className,
      )}
    >
      {metrics.map((m) => {
        const dir = m.change != null ? changeDirection(m.change) : 'neutral';

        return (
          <div
            key={m.label}
            className="terminal-panel flex flex-col gap-1"
          >
            {/* Label */}
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                lineHeight: '1.2',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {m.label}
            </span>

            {/* Hero value + change */}
            <div className="flex items-baseline gap-2">
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-2xl)',
                  fontWeight: 600,
                  color: 'var(--color-text-primary)',
                  lineHeight: '1.2',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {m.value}
              </span>

              {m.change != null && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-sm)',
                    color: changeColor(dir),
                    fontVariantNumeric: 'tabular-nums',
                    lineHeight: '1.2',
                  }}
                >
                  {changeArrow(dir) && (
                    <span style={{ fontSize: '8px', marginRight: '2px' }}>
                      {changeArrow(dir)}
                    </span>
                  )}
                  {formatChange(m.change)}
                </span>
              )}
            </div>

            {/* Sub-value */}
            {m.subValue && (
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  lineHeight: '1.3',
                }}
              >
                {m.subValue}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
