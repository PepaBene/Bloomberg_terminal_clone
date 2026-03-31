import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface NewIssue {
  issuer: string;
  coupon: number;
  maturity: string;
  size: string;
  rating: string;
  spread: number;
  initialTalk: number;
  status: 'priced' | 'launched' | 'upcoming';
}

export interface NewIssueTableProps {
  issues: NewIssue[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const STATUS_MAP: Record<
  NewIssue['status'],
  { label: string; badgeClass: string }
> = {
  priced: { label: 'PRICED', badgeClass: 'terminal-badge terminal-badge-positive' },
  launched: { label: 'LAUNCHED', badgeClass: 'terminal-badge terminal-badge-accent' },
  upcoming: { label: 'UPCOMING', badgeClass: 'terminal-badge terminal-badge-neutral' },
};

function spreadVsTalk(spread: number, talk: number): { badgeClass: string; label: string } {
  const diff = spread - talk;
  const tighter = diff < 0;
  if (tighter) {
    return {
      badgeClass: 'terminal-badge terminal-badge-positive',
      label: `${Math.abs(diff).toFixed(0)}bp tighter`,
    };
  }
  if (diff > 0) {
    return {
      badgeClass: 'terminal-badge terminal-badge-negative',
      label: `${diff.toFixed(0)}bp wider`,
    };
  }
  return {
    badgeClass: 'terminal-badge terminal-badge-neutral',
    label: 'flat',
  };
}

function fmtBps(v: number): string {
  return `${v.toFixed(0)}`;
}

/** Map credit rating to quality-tier color */
function ratingColor(rating: string): string {
  const r = rating.toUpperCase();
  if (r.startsWith('AAA') || r.startsWith('AA')) return 'var(--color-quality-5)';
  if (r.startsWith('A')) return 'var(--color-quality-4)';
  if (r.startsWith('BBB')) return 'var(--color-quality-3)';
  if (r.startsWith('BB')) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function NewIssueTable({ issues, className }: NewIssueTableProps) {
  return (
    <div className={clsx('animate-in overflow-auto', className)}>
      <table className="terminal-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Issuer</th>
            <th className="right">Coupon</th>
            <th className="right">Maturity</th>
            <th className="right">Size</th>
            <th style={{ textAlign: 'left' }}>Rating</th>
            <th className="right">Spread</th>
            <th className="right">Talk</th>
            <th style={{ textAlign: 'left' }}>vs Talk</th>
            <th style={{ textAlign: 'left' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((iss, i) => {
            const vt = spreadVsTalk(iss.spread, iss.initialTalk);
            const statusCfg = STATUS_MAP[iss.status];

            return (
              <tr key={`${iss.issuer}-${i}`}>
                {/* Issuer */}
                <td
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {iss.issuer}
                </td>

                {/* Coupon */}
                <td
                  className="right"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {iss.coupon.toFixed(3)}%
                </td>

                {/* Maturity */}
                <td
                  className="right"
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                  }}
                >
                  {iss.maturity}
                </td>

                {/* Size */}
                <td
                  className="right"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {iss.size}
                </td>

                {/* Rating -- quality-tier coloring */}
                <td
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontWeight: 500,
                    color: ratingColor(iss.rating),
                  }}
                >
                  {iss.rating}
                </td>

                {/* Spread */}
                <td
                  className="right"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {fmtBps(iss.spread)}
                </td>

                {/* Initial Talk */}
                <td
                  className="right"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--color-text-tertiary)',
                  }}
                >
                  {fmtBps(iss.initialTalk)}
                </td>

                {/* vs Talk badge -- 15% opacity background */}
                <td>
                  <span className={vt.badgeClass}>
                    {vt.label}
                  </span>
                </td>

                {/* Status badge */}
                <td>
                  <span className={statusCfg.badgeClass}>
                    {statusCfg.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
