import { useMemo } from 'react';
import clsx from 'clsx';
import { SparklineCell } from '@/components/ui/SparklineCell';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CountryRisk {
  code: string;
  name: string;
  composite: number;
  political: number;
  economic: number;
  sanctions: number;
  classification: string;
  trend: string;
  history: number[];
}

export interface CountryRiskRankingProps {
  countries: CountryRisk[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CLASSIFICATION_COLORS: Record<string, string> = {
  LOW: 'var(--color-signal-positive)',
  MODERATE: 'var(--color-accent-primary)',
  ELEVATED: 'var(--color-signal-warning)',
  HIGH: 'var(--color-signal-negative)',
  EXTREME: '#B91C1C',
};

function classificationColor(c: string): string {
  return CLASSIFICATION_COLORS[c.toUpperCase()] ?? 'var(--color-signal-neutral)';
}

interface TrendInfo {
  arrow: string;
  color: string;
}

function trendInfo(trend: string): TrendInfo {
  const t = trend.toLowerCase();
  if (t === 'improving') return { arrow: '\u2191', color: 'var(--color-signal-positive)' };
  if (t === 'deteriorating') return { arrow: '\u2193', color: 'var(--color-signal-negative)' };
  return { arrow: '\u2192', color: 'var(--color-signal-neutral)' };
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CountryRiskRanking({
  countries,
  className,
}: CountryRiskRankingProps) {
  const sorted = useMemo(
    () => [...countries].sort((a, b) => b.composite - a.composite),
    [countries],
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
            {[
              'Country',
              'Composite',
              'Political',
              'Economic',
              'Sanctions',
              'Classification',
              'Trend',
              '6M History',
            ].map((h) => (
              <th
                key={h}
                style={{
                  textAlign:
                    h === 'Country' || h === 'Classification' || h === 'Trend' || h === '6M History'
                      ? 'left'
                      : 'right',
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
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const clsColor = classificationColor(c.classification);
            const ti = trendInfo(c.trend);

            return (
              <tr
                key={c.code}
                style={{
                  borderBottom: '1px solid var(--color-surface-border)',
                }}
              >
                {/* Country */}
                <td
                  style={{
                    padding: '6px 8px',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ color: 'var(--color-text-tertiary)', marginRight: '6px' }}>
                    {c.code}
                  </span>
                  <span style={{ color: 'var(--color-text-primary)' }}>{c.name}</span>
                </td>

                {/* Composite */}
                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontWeight: 600,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {c.composite.toFixed(1)}
                </td>

                {/* Political */}
                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-secondary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {c.political.toFixed(1)}
                </td>

                {/* Economic */}
                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-secondary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {c.economic.toFixed(1)}
                </td>

                {/* Sanctions */}
                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-secondary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {c.sanctions.toFixed(1)}
                </td>

                {/* Classification badge */}
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      color: clsColor,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '2px 8px',
                      border: `1px solid ${clsColor}`,
                      borderRadius: '9999px',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {c.classification}
                  </span>
                </td>

                {/* Trend arrow */}
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      color: ti.color,
                      fontWeight: 600,
                      fontSize: 'var(--text-md)',
                    }}
                  >
                    {ti.arrow}
                  </span>
                </td>

                {/* Sparkline */}
                <td style={{ padding: '6px 8px' }}>
                  {c.history.length >= 2 ? (
                    <SparklineCell
                      data={c.history}
                      width={60}
                      height={20}
                      positive={c.history[c.history.length - 1]! < c.history[0]!}
                    />
                  ) : (
                    <span style={{ color: 'var(--color-text-tertiary)' }}>{'\u2014'}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
