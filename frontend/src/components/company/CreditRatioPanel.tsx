import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CreditRatio {
  name: string;
  value: number;
  peerMedian?: number;
  trend: 'improving' | 'stable' | 'deteriorating';
}

export interface CreditRatioPanelProps {
  ratios: CreditRatio[];
  category: 'leverage' | 'coverage' | 'liquidity';
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CATEGORY_TITLES: Record<string, string> = {
  leverage: 'Leverage Ratios',
  coverage: 'Coverage Ratios',
  liquidity: 'Liquidity Ratios',
};

function trendArrow(trend: CreditRatio['trend']): string {
  if (trend === 'improving') return '\u25B2';
  if (trend === 'deteriorating') return '\u25BC';
  return '\u25C6';
}

function trendColor(trend: CreditRatio['trend']): string {
  if (trend === 'improving') return 'var(--color-signal-positive)';
  if (trend === 'deteriorating') return 'var(--color-signal-negative)';
  return 'var(--color-signal-neutral)';
}

/**
 * Determine whether a ratio value is concerning.
 * Simple heuristic: deteriorating trend gets warning highlight.
 */
function valueColor(ratio: CreditRatio): string {
  if (ratio.trend === 'deteriorating') return 'var(--color-signal-warning)';
  return 'var(--color-text-primary)';
}

function fmtVal(v: number): string {
  return v.toFixed(2);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CreditRatioPanel({
  ratios,
  category,
  className,
}: CreditRatioPanelProps) {
  const title = CATEGORY_TITLES[category] ?? category;

  return (
    <div className={clsx('terminal-panel flex flex-col gap-2', className)}>
      <h3 className="terminal-section-title">{title}</h3>

      <table className="terminal-table">
        <thead>
          <tr>
            <th>Ratio</th>
            <th className="right">Current</th>
            <th className="right">Peer Median</th>
            <th className="right">Trend</th>
          </tr>
        </thead>
        <tbody>
          {ratios.map((r) => (
            <tr key={r.name}>
              <td
                style={{
                  fontFamily: 'var(--font-ui)',
                  color: 'var(--color-text-primary)',
                }}
              >
                {r.name}
              </td>
              <td
                className="right"
                style={{ color: valueColor(r) }}
              >
                {fmtVal(r.value)}
              </td>
              <td
                className="right"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {r.peerMedian != null ? fmtVal(r.peerMedian) : '\u2014'}
              </td>
              <td className="right">
                <span
                  style={{
                    color: trendColor(r.trend),
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                  }}
                >
                  <span style={{ fontSize: '8px', marginRight: '3px' }}>
                    {trendArrow(r.trend)}
                  </span>
                  {r.trend}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
