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

const TYPE_COLORS: Record<InsiderTransaction['type'], string> = {
  BUY: 'var(--color-signal-positive)',
  SELL: 'var(--color-signal-negative)',
  EXERCISE: 'var(--color-signal-neutral)',
};

const SIGNAL_COLORS: Record<string, string> = {
  CLUSTER_BUY: 'var(--color-signal-positive)',
  CEO_PURCHASE: 'var(--color-signal-positive)',
  UNUSUAL_SALE: 'var(--color-signal-negative)',
};

const SIGNAL_SEVERITY_COLORS: Record<string, string> = {
  positive: 'var(--color-signal-positive)',
  negative: 'var(--color-signal-negative)',
  neutral: 'var(--color-signal-neutral)',
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
            {COLUMNS.map((h) => (
              <th
                key={h}
                style={{
                  textAlign: h === 'Date' || h === 'Insider' || h === 'Title' || h === 'Type' || h === 'Signal' ? 'left' : 'right',
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
          {grouped.map(([insiderName, txs]) => (
            <InsiderGroup
              key={insiderName}
              transactions={txs}
              signalMap={signalMap}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Insider group rows                                                 */
/* ------------------------------------------------------------------ */

function InsiderGroup({
  transactions,
  signalMap,
}: {
  transactions: InsiderTransaction[];
  signalMap: Map<string, InsiderSignal>;
}) {
  return (
    <>
      {transactions.map((tx, idx) => {
        const signal = signalMap.get(tx.id);
        const sigColor = signal
          ? (SIGNAL_COLORS[signal.signal] ??
            SIGNAL_SEVERITY_COLORS[signal.severity] ??
            'var(--color-text-tertiary)')
          : undefined;

        return (
          <tr
            key={tx.id}
            style={{
              borderBottom: '1px solid var(--color-surface-border)',
              borderTop: idx === 0 ? '2px solid var(--color-surface-border)' : undefined,
            }}
          >
            {/* Date */}
            <td style={cellStyle}>{tx.date}</td>

            {/* Insider */}
            <td
              style={{
                ...cellStyle,
                fontFamily: 'var(--font-ui)',
                fontWeight: idx === 0 ? 600 : 400,
                color: 'var(--color-text-primary)',
              }}
            >
              {idx === 0 ? tx.insiderName : ''}
            </td>

            {/* Title */}
            <td
              style={{
                ...cellStyle,
                fontFamily: 'var(--font-ui)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {idx === 0 ? tx.title : ''}
            </td>

            {/* Type badge */}
            <td style={cellStyle}>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  color: TYPE_COLORS[tx.type],
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  padding: '2px 8px',
                  border: `1px solid ${TYPE_COLORS[tx.type]}`,
                  borderRadius: '9999px',
                  whiteSpace: 'nowrap',
                }}
              >
                {tx.type}
              </span>
            </td>

            {/* Shares */}
            <td style={{ ...cellStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {formatShares(tx.shares)}
            </td>

            {/* Price */}
            <td style={{ ...cellStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              ${tx.price.toFixed(2)}
            </td>

            {/* Value */}
            <td style={{ ...cellStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {formatCurrency(tx.value)}
            </td>

            {/* Signal */}
            <td style={cellStyle}>
              {signal && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    color: sigColor,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '2px 8px',
                    border: `1px solid ${sigColor}`,
                    borderRadius: '9999px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {signal.signal}
                </span>
              )}
            </td>
          </tr>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const cellStyle: React.CSSProperties = {
  padding: '6px 8px',
  color: 'var(--color-text-primary)',
  whiteSpace: 'nowrap',
};
