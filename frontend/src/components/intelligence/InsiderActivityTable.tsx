import { useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface InsiderTransaction {
  id: string;
  date: string;
  insiderName: string;
  title: string;
  type: 'BUY' | 'SELL' | 'EXERCISE';
  shares: number;
  price: number;
  value: number;
}

export interface InsiderSignal {
  transactionId: string;
  signal: string;
  severity: 'positive' | 'negative' | 'neutral';
}

export interface InsiderActivityTableProps {
  transactions: InsiderTransaction[];
  signals?: InsiderSignal[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const TYPE_BADGE: Record<InsiderTransaction['type'], { color: string; bg: string }> = {
  BUY: {
    color: 'var(--signal-positive)',
    bg: 'color-mix(in srgb, var(--signal-positive) 15%, transparent)',
  },
  SELL: {
    color: 'var(--signal-negative)',
    bg: 'color-mix(in srgb, var(--signal-negative) 15%, transparent)',
  },
  EXERCISE: {
    color: 'var(--text-tertiary)',
    bg: 'color-mix(in srgb, var(--text-tertiary) 15%, transparent)',
  },
};

const SIGNAL_STYLE: Record<string, { color: string; pulse?: boolean }> = {
  CLUSTER_BUY: { color: 'var(--signal-positive)', pulse: true },
  CEO_PURCHASE: { color: 'var(--accent-primary)' },
  UNUSUAL_SALE: { color: 'var(--signal-negative)' },
};

const SIGNAL_SEVERITY_COLORS: Record<string, string> = {
  positive: 'var(--signal-positive)',
  negative: 'var(--signal-negative)',
  neutral: 'var(--signal-neutral)',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatCurrency(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

function formatShares(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toLocaleString();
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function InsiderActivityTable({
  transactions,
  signals,
  className,
}: InsiderActivityTableProps) {
  /** Build a signal lookup by transaction id */
  const signalMap = useMemo(() => {
    const map = new Map<string, InsiderSignal>();
    signals?.forEach((s) => map.set(s.transactionId, s));
    return map;
  }, [signals]);

  /** Group transactions by insider */
  const grouped = useMemo(() => {
    const groups = new Map<string, InsiderTransaction[]>();
    for (const tx of transactions) {
      const existing = groups.get(tx.insiderName);
      if (existing) {
        existing.push(tx);
      } else {
        groups.set(tx.insiderName, [tx]);
      }
    }
    return Array.from(groups.entries());
  }, [transactions]);

  const COLUMNS = ['Date', 'Insider', 'Title', 'Type', 'Shares', 'Price', 'Value', 'Signal'];

  return (
    <div
      className={clsx('animate-in', className)}
      style={{ overflow: 'auto' }}
    >
      <table className="terminal-table">
        <thead>
          <tr>
            {COLUMNS.map((h) => (
              <th
                key={h}
                className={
                  h === 'Shares' || h === 'Price' || h === 'Value' ? 'right' : undefined
                }
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grouped.map(([insiderName, txs]) => (
            <InsiderGroup
              key={insiderName}
              insiderName={insiderName}
              transactions={txs}
              signalMap={signalMap}
            />
          ))}
        </tbody>
      </table>

      {/* Signal pulse animation */}
      <style>{`
        @keyframes signalPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Insider group rows                                                 */
/* ------------------------------------------------------------------ */

function InsiderGroup({
  insiderName,
  transactions,
  signalMap,
}: {
  insiderName: string;
  transactions: InsiderTransaction[];
  signalMap: Map<string, InsiderSignal>;
}) {
  return (
    <>
      {/* Group header */}
      <tr>
        <td
          colSpan={8}
          className="group-row"
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            background: 'var(--surface-overlay)',
            padding: 'var(--space-1) var(--space-2)',
            fontWeight: 600,
            letterSpacing: '0.05em',
          }}
        >
          {insiderName} &mdash; {transactions[0]?.title}
        </td>
      </tr>

      {transactions.map((tx) => {
        const signal = signalMap.get(tx.id);
        const sigStyle = signal
          ? SIGNAL_STYLE[signal.signal] ?? {
              color: SIGNAL_SEVERITY_COLORS[signal.severity] ?? 'var(--text-tertiary)',
            }
          : undefined;

        return (
          <tr key={tx.id}>
            {/* Date */}
            <td style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
              {tx.date}
            </td>

            {/* Insider — hidden in group view */}
            <td
              style={{
                fontFamily: 'var(--font-ui)',
                color: 'var(--text-primary)',
              }}
            />

            {/* Title */}
            <td
              style={{
                fontFamily: 'var(--font-ui)',
                color: 'var(--text-secondary)',
              }}
            />

            {/* Type badge */}
            <td>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  fontVariantNumeric: 'tabular-nums',
                  color: TYPE_BADGE[tx.type].color,
                  background: TYPE_BADGE[tx.type].bg,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  padding: '2px var(--space-2)',
                  borderRadius: 'var(--radius-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {tx.type}
              </span>
            </td>

            {/* Shares */}
            <td className="right" style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
              {formatShares(tx.shares)}
            </td>

            {/* Price */}
            <td className="right" style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
              ${tx.price.toFixed(2)}
            </td>

            {/* Value */}
            <td className="right" style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
              {formatCurrency(tx.value)}
            </td>

            {/* Signal */}
            <td>
              {signal && sigStyle && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    fontVariantNumeric: 'tabular-nums',
                    color: sigStyle.color,
                    background: `color-mix(in srgb, ${sigStyle.color} 15%, transparent)`,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '2px var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                    whiteSpace: 'nowrap',
                    animation: sigStyle.pulse ? 'signalPulse 2s ease-in-out infinite' : undefined,
                  }}
                >
                  {signal.signal.replace(/_/g, ' ')}
                </span>
              )}
            </td>
          </tr>
        );
      })}
    </>
  );
}
