import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SpreadRow {
  name: string;
  value: number;
  change1d: number;
  change1w: number;
  percentile: number;
}

export interface KeySpreadsPanelProps {
  spreads: SpreadRow[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Widening = red (negative for credit), tightening = green */
function changeColor(v: number): string {
  if (v > 0) return 'var(--color-signal-negative)';
  if (v < 0) return 'var(--color-signal-positive)';
  return 'var(--color-signal-neutral)';
}

function changeArrow(v: number): string {
  if (v > 0) return '\u2191';
  if (v < 0) return '\u2193';
  return '';
}

function formatBps(v: number): string {
  return v.toFixed(0);
}

function formatChange(v: number): string {
  const sign = v > 0 ? '+' : '';
  return `${changeArrow(v)}${sign}${v.toFixed(1)}`;
}

/** Quality-tier coloring for percentile bars:
 *  Low percentile (tight spreads) = quality-5 (green)
 *  High percentile (wide spreads) = quality-1 (red) */
function percentileColor(p: number): string {
  if (p >= 80) return 'var(--color-quality-1)';
  if (p >= 60) return 'var(--color-quality-2)';
  if (p >= 40) return 'var(--color-quality-3)';
  if (p >= 20) return 'var(--color-quality-4)';
  return 'var(--color-quality-5)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function KeySpreadsPanel({ spreads, className }: KeySpreadsPanelProps) {
  return (
    <div className={clsx('animate-in overflow-auto', className)}>
      <table className="terminal-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Name</th>
            <th className="right">Value (bps)</th>
            <th className="right">1D Chg</th>
            <th className="right">1W Chg</th>
            <th className="right" style={{ minWidth: 120 }}>1Y Percentile</th>
          </tr>
        </thead>
        <tbody>
          {spreads.map((s) => (
            <tr key={s.name}>
              {/* Name */}
              <td
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {s.name}
              </td>

              {/* Value */}
              <td className="right" style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)' }}>
                {formatBps(s.value)}
              </td>

              {/* 1D Change */}
              <td
                className="right"
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                  color: changeColor(s.change1d),
                }}
              >
                {formatChange(s.change1d)}
              </td>

              {/* 1W Change */}
              <td
                className="right"
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                  color: changeColor(s.change1w),
                }}
              >
                {formatChange(s.change1w)}
              </td>

              {/* Percentile bar */}
              <td className="right">
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    minWidth: 100,
                  }}
                >
                  <div
                    style={{
                      flex: 1,
                      height: 4,
                      background: 'var(--color-surface-border)',
                      borderRadius: 'var(--radius-sm)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max(0, Math.min(100, s.percentile))}%`,
                        height: '100%',
                        background: percentileColor(s.percentile),
                        borderRadius: 'var(--radius-sm)',
                        transition: 'width 300ms ease',
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontVariantNumeric: 'tabular-nums',
                      color: percentileColor(s.percentile),
                      fontSize: 'var(--text-xs)',
                      minWidth: 28,
                      textAlign: 'right',
                    }}
                  >
                    {s.percentile}%
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
