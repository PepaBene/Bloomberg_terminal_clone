import { useMemo } from 'react';
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

function formatBps(v: number): string {
  return v.toFixed(0);
}

function formatChange(v: number): string {
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}`;
}

function percentileColor(p: number): string {
  if (p >= 80) return 'var(--color-signal-negative)';
  if (p >= 60) return 'var(--color-signal-warning)';
  if (p >= 40) return 'var(--color-signal-neutral)';
  if (p >= 20) return 'var(--color-signal-positive)';
  return 'var(--color-signal-positive)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function KeySpreadsPanel({ spreads, className }: KeySpreadsPanelProps) {
  const rows = useMemo(() => spreads, [spreads]);

  return (
    <div className={clsx('overflow-auto', className)}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
        }}
      >
        <thead>
          <tr>
            {['Name', 'Value (bps)', '1D Chg', '1W Chg', '1Y Percentile'].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    textAlign: h === 'Name' ? 'left' : 'right',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    color: 'var(--color-text-secondary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    padding: '6px 8px',
                    borderBottom: '1px solid var(--color-surface-border)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr
              key={s.name}
              style={{ borderBottom: '1px solid var(--color-surface-border)' }}
            >
              {/* Name */}
              <td
                style={{
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {s.name}
              </td>

              {/* Value */}
              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatBps(s.value)}
              </td>

              {/* 1D Change */}
              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: changeColor(s.change1d),
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatChange(s.change1d)}
              </td>

              {/* 1W Change */}
              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: changeColor(s.change1w),
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatChange(s.change1w)}
              </td>

              {/* Percentile bar */}
              <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                <div
                  className="inline-flex items-center gap-2"
                  style={{ minWidth: '90px' }}
                >
                  <div
                    style={{
                      flex: 1,
                      height: '4px',
                      background: 'var(--color-surface-border)',
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max(0, Math.min(100, s.percentile))}%`,
                        height: '100%',
                        background: percentileColor(s.percentile),
                        borderRadius: '2px',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontVariantNumeric: 'tabular-nums',
                      color: percentileColor(s.percentile),
                      fontSize: 'var(--text-xs)',
                      minWidth: '28px',
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
