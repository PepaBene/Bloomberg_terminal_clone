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

function statusBadgeClass(status: 'upcoming' | 'completed'): string {
  return status === 'completed'
    ? 'terminal-badge terminal-badge-positive'
    : 'terminal-badge terminal-badge-neutral';
}

function statusLabel(status: 'upcoming' | 'completed'): string {
  return status === 'completed' ? 'COMPLETED' : 'UPCOMING';
}

/** Bid-to-cover conditional coloring: >2.5 green, <2.0 red, otherwise neutral */
function bidToCoverColor(btc: number): string {
  if (btc > 2.5) return 'var(--color-signal-positive)';
  if (btc < 2.0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
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
    <div className={clsx('animate-in overflow-auto', className)}>
      <table className="terminal-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Date</th>
            <th style={{ textAlign: 'left' }}>Security</th>
            <th className="right">Size</th>
            <th className="right">Bid-to-Cover</th>
            <th className="right">Tail (bps)</th>
            <th style={{ textAlign: 'left' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {auctions.map((a, i) => (
            <tr key={`${a.date}-${a.security}-${i}`}>
              {/* Date */}
              <td
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {a.date}
              </td>

              {/* Security */}
              <td
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                }}
              >
                {a.security}
              </td>

              {/* Size */}
              <td
                className="right"
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {a.size}
              </td>

              {/* Bid-to-Cover -- conditional coloring */}
              <td
                className="right"
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                  color:
                    a.status === 'completed' && a.bidToCover != null
                      ? bidToCoverColor(a.bidToCover)
                      : 'var(--color-text-tertiary)',
                }}
              >
                {a.status === 'completed' && a.bidToCover != null
                  ? a.bidToCover.toFixed(2)
                  : '\u2014'}
              </td>

              {/* Tail */}
              <td
                className="right"
                style={{
                  fontFamily: 'var(--font-data)',
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

              {/* Status badge */}
              <td>
                <span className={statusBadgeClass(a.status)}>
                  {statusLabel(a.status)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
