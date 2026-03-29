import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface AuctionRecord {
  date: string;
  security: string;
  size: string;
  bidToCover?: number;
  tailBps?: number;
  status: 'upcoming' | 'completed';
}

export interface TreasuryAuctionCalendarProps {
  auctions: AuctionRecord[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function statusBadge(status: 'upcoming' | 'completed') {
  const isCompleted = status === 'completed';
  const color = isCompleted
    ? 'var(--color-signal-positive)'
    : 'var(--color-signal-neutral)';
  const label = isCompleted ? 'COMPLETED' : 'UPCOMING';

  return (
    <span
      style={{
        fontFamily: 'var(--font-data)',
        fontSize: 'var(--text-xs)',
        fontWeight: 500,
        color,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        padding: '2px 8px',
        border: `1px solid ${color}`,
        borderRadius: '9999px',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}

function tailColor(tailBps: number): string {
  if (tailBps <= 0) return 'var(--color-signal-positive)';
  if (tailBps <= 1) return 'var(--color-signal-neutral)';
  return 'var(--color-signal-negative)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function TreasuryAuctionCalendar({
  auctions,
  className,
}: TreasuryAuctionCalendarProps) {
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
            {['Date', 'Security', 'Size', 'Bid-to-Cover', 'Tail (bps)', 'Status'].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    textAlign:
                      h === 'Date' || h === 'Security' || h === 'Status'
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
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {auctions.map((a, i) => (
            <tr
              key={`${a.date}-${a.security}-${i}`}
              style={{ borderBottom: '1px solid var(--color-surface-border)' }}
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
                {a.date}
              </td>

              <td
                style={{
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                }}
              >
                {a.security}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {a.size}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  fontVariantNumeric: 'tabular-nums',
                  color:
                    a.status === 'completed' && a.bidToCover != null
                      ? 'var(--color-text-primary)'
                      : 'var(--color-text-tertiary)',
                }}
              >
                {a.status === 'completed' && a.bidToCover != null
                  ? a.bidToCover.toFixed(2)
                  : '\u2014'}
              </td>

              <td
                style={{
                  textAlign: 'right',
                  padding: '6px 8px',
                  fontVariantNumeric: 'tabular-nums',
                  color:
                    a.status === 'completed' && a.tailBps != null
                      ? tailColor(a.tailBps)
                      : 'var(--color-text-tertiary)',
                }}
              >
                {a.status === 'completed' && a.tailBps != null
                  ? a.tailBps.toFixed(1)
                  : '\u2014'}
              </td>

              <td style={{ padding: '6px 8px' }}>{statusBadge(a.status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
