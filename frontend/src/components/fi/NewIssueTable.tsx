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
  { label: string; color: string }
> = {
  priced: { label: 'PRICED', color: 'var(--color-signal-positive)' },
  launched: { label: 'LAUNCHED', color: 'var(--color-accent-primary)' },
  upcoming: { label: 'UPCOMING', color: 'var(--color-signal-neutral)' },
};

function spreadVsTalk(spread: number, talk: number) {
  const diff = spread - talk;
  const tighter = diff < 0;
  const color = tighter
    ? 'var(--color-signal-positive)'
    : diff > 0
      ? 'var(--color-signal-negative)'
      : 'var(--color-signal-neutral)';
  const label = tighter
    ? `${Math.abs(diff).toFixed(0)}bp tighter`
    : diff > 0
      ? `${diff.toFixed(0)}bp wider`
      : 'flat';
  return { color, label };
}

function fmtBps(v: number): string {
  return `${v.toFixed(0)}`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function NewIssueTable({ issues, className }: NewIssueTableProps) {
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
              'Issuer',
              'Coupon',
              'Maturity',
              'Size',
              'Rating',
              'Spread',
              'Talk',
              'vs Talk',
              'Status',
            ].map((h) => (
              <th
                key={h}
                style={{
                  textAlign:
                    h === 'Issuer' || h === 'Rating' || h === 'Status' || h === 'vs Talk'
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
          {issues.map((iss, i) => {
            const vt = spreadVsTalk(iss.spread, iss.initialTalk);
            const statusCfg = STATUS_MAP[iss.status];

            return (
              <tr
                key={`${iss.issuer}-${i}`}
                style={{
                  borderBottom: '1px solid var(--color-surface-border)',
                }}
              >
                <td
                  style={{
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {iss.issuer}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {iss.coupon.toFixed(3)}%
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                  }}
                >
                  {iss.maturity}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {iss.size}
                </td>

                <td
                  style={{
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {iss.rating}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {fmtBps(iss.spread)}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-tertiary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {fmtBps(iss.initialTalk)}
                </td>

                {/* vs Talk badge */}
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      color: vt.color,
                      padding: '2px 8px',
                      border: `1px solid ${vt.color}`,
                      borderRadius: '9999px',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {vt.label}
                  </span>
                </td>

                {/* Status badge */}
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      color: statusCfg.color,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '2px 8px',
                      border: `1px solid ${statusCfg.color}`,
                      borderRadius: '9999px',
                      whiteSpace: 'nowrap',
                    }}
                  >
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
