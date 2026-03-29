import { useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MacroIndicator {
  name: string;
  actual: number;
  prior: number;
  forecast: number;
  surprise: number;
  releaseDate: string;
}

export interface MacroIndicatorTableProps {
  indicators: MacroIndicator[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function surpriseColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-signal-neutral)';
}

function formatNum(v: number): string {
  return v.toFixed(1);
}

function formatSurprise(v: number): string {
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function MacroIndicatorTable({
  indicators,
  className,
}: MacroIndicatorTableProps) {
  /** Sort by release date descending */
  const sorted = useMemo(
    () =>
      [...indicators].sort(
        (a, b) => new Date(b.releaseDate).getTime() - new Date(a.releaseDate).getTime(),
      ),
    [indicators],
  );

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
            {['Release', 'Indicator', 'Actual', 'Prior', 'Forecast', 'Surprise'].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    textAlign:
                      h === 'Release' || h === 'Indicator' ? 'left' : 'right',
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
          {sorted.map((ind) => (
            <tr
              key={`${ind.name}-${ind.releaseDate}`}
              style={{ borderBottom: '1px solid var(--color-surface-border)' }}
            >
              <td
                style={{
                  padding: '6px 8px',
                  color: 'var(--color-text-tertiary)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  whiteSpace: 'nowrap',
                }}
              >
                {ind.releaseDate}
              </td>

              <td
                style={{
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {ind.name}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                }}
              >
                {formatNum(ind.actual)}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: 'var(--color-text-secondary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatNum(ind.prior)}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: 'var(--color-text-secondary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatNum(ind.forecast)}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                  color: surpriseColor(ind.surprise),
                }}
              >
                {formatSurprise(ind.surprise)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
