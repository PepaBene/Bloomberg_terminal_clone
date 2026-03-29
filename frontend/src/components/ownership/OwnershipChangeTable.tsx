import { useState, useCallback, useMemo } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface OwnershipChange {
  holder: string;
  priorShares: number;
  currentShares: number;
  change: number;
  changePct: number;
  filingDate: string;
}

export interface OwnershipChangeTableProps {
  changes: OwnershipChange[];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

type SortKey = keyof OwnershipChange;
type SortDir = 'asc' | 'desc';

function fmtShares(n: number): string {
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toLocaleString();
}

function fmtPct(n: number): string {
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

function changeColor(val: number): string {
  if (val > 0) return 'var(--color-signal-positive)';
  if (val < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

/* ------------------------------------------------------------------ */
/*  Column definitions                                                 */
/* ------------------------------------------------------------------ */

interface ColDef {
  key: SortKey;
  label: string;
  align: 'left' | 'right';
}

const COLUMNS: ColDef[] = [
  { key: 'holder', label: 'Holder', align: 'left' },
  { key: 'priorShares', label: 'Prior Shares', align: 'right' },
  { key: 'currentShares', label: 'Current Shares', align: 'right' },
  { key: 'change', label: 'Change', align: 'right' },
  { key: 'changePct', label: 'Change %', align: 'right' },
  { key: 'filingDate', label: 'Filing Date', align: 'right' },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function OwnershipChangeTable({ changes }: OwnershipChangeTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('changePct');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  const sorted = useMemo(() => {
    const copy = [...changes];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      let cmp = 0;
      if (typeof av === 'number' && typeof bv === 'number') {
        cmp = av - bv;
      } else {
        cmp = String(av).localeCompare(String(bv));
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [changes, sortKey, sortDir]);

  return (
    <div className="terminal-panel flex flex-col gap-3">
      {/* Header */}
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Ownership Changes
      </div>

      <div style={{ overflow: 'auto' }}>
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
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    textAlign: col.align,
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border-strong)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color:
                      sortKey === col.key
                        ? 'var(--color-text-primary)'
                        : 'var(--color-text-secondary)',
                    cursor: 'pointer',
                    userSelect: 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span style={{ marginLeft: 4, fontSize: 8 }}>
                      {sortDir === 'asc' ? '\u25B2' : '\u25BC'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, idx) => (
              <tr
                key={`${row.holder}-${idx}`}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--color-surface-overlay)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
                style={{ transition: 'background 0.1s' }}
              >
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-ui)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {row.holder}
                </td>
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {fmtShares(row.priorShares)}
                </td>
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {fmtShares(row.currentShares)}
                </td>
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    color: changeColor(row.change),
                  }}
                >
                  {row.change > 0 ? '+' : ''}{fmtShares(row.change)}
                </td>
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    fontWeight: 600,
                    color: changeColor(row.changePct),
                  }}
                >
                  {fmtPct(row.changePct)}
                </td>
                <td
                  style={{
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    textAlign: 'right',
                    color: 'var(--color-text-tertiary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {row.filingDate}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
