import { useState, useCallback, type ReactNode } from 'react';
import clsx from 'clsx';

/* ── Public types ─────────────────────────────────────────── */

export interface Column<T> {
  /** Unique column key, used to look up values on each row */
  key: string;
  /** Display name shown in header */
  name: string;
  /** Cell alignment (default: left) */
  align?: 'left' | 'center' | 'right';
  /** Optional formatter — receives the raw cell value and the full row */
  format?: (value: unknown, row: T) => ReactNode;
  /** Whether this column is sortable (default: inherits from table) */
  sortable?: boolean;
  /** Column width (CSS value) */
  width?: string;
}

export interface DataTableProps<T> {
  /** Column definitions */
  columns: Column<T>[];
  /** Row data array */
  data: T[];
  /** Row click handler — receives the row and its index */
  onRowClick?: (row: T, index: number) => void;
  /** Use compact (22px) row height instead of standard (28px) */
  compact?: boolean;
  /** Enable sorting on all columns (individual columns can override) */
  sortable?: boolean;
  /** Additional CSS class */
  className?: string;
  /** Row key accessor — defaults to index */
  rowKey?: (row: T, index: number) => string | number;
}

type SortDir = 'asc' | 'desc' | null;

/* ── Component ────────────────────────────────────────────── */

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  compact = false,
  sortable = false,
  className,
  rowKey,
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = useCallback(
    (key: string) => {
      if (sortCol === key) {
        // Cycle: asc -> desc -> null
        setSortDir((prev) =>
          prev === 'asc' ? 'desc' : prev === 'desc' ? null : 'asc',
        );
        if (sortDir === 'desc') setSortCol(null);
      } else {
        setSortCol(key);
        setSortDir('asc');
      }
    },
    [sortCol, sortDir],
  );

  /* ── Sorted data ──────────────────────────────────────── */
  const sorted = (() => {
    if (!sortCol || !sortDir) return data;
    const copy = [...data];
    copy.sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number')
        return sortDir === 'asc' ? av - bv : bv - av;
      const sa = String(av);
      const sb = String(bv);
      return sortDir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
    return copy;
  })();

  const rowHeight = compact
    ? 'var(--table-row-height-sm)'
    : 'var(--table-row-height)';

  return (
    <div className={clsx('overflow-auto', className)}>
      <table
        className="w-full border-collapse"
        style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)' }}
      >
        {/* Sticky header */}
        <thead>
          <tr>
            {columns.map((col) => {
              const isSortable =
                col.sortable !== undefined ? col.sortable : sortable;
              const isActive = sortCol === col.key && sortDir !== null;

              return (
                <th
                  key={col.key}
                  className={clsx(
                    'sticky top-0 z-10 whitespace-nowrap font-medium',
                    isSortable && 'cursor-pointer select-none',
                  )}
                  style={{
                    height: rowHeight,
                    padding: `var(--table-cell-py) var(--table-cell-px)`,
                    textAlign: col.align ?? 'left',
                    background: 'var(--color-surface-base)',
                    borderBottom: '1px solid var(--color-surface-border-strong)',
                    color: isActive
                      ? 'var(--color-text-primary)'
                      : 'var(--color-text-secondary)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    width: col.width,
                  }}
                  onClick={isSortable ? () => handleSort(col.key) : undefined}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.name}
                    {isSortable && (
                      <SortIndicator
                        active={isActive}
                        direction={isActive ? sortDir : null}
                      />
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {sorted.map((row, idx) => (
            <tr
              key={rowKey ? rowKey(row, idx) : idx}
              className={clsx(onRowClick && 'cursor-pointer')}
              style={{
                height: rowHeight,
                transition: 'background 0.1s',
              }}
              onClick={onRowClick ? () => onRowClick(row, idx) : undefined}
              onMouseEnter={(e) => {
                e.currentTarget.style.background =
                  'var(--color-surface-overlay)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {columns.map((col) => {
                const raw = row[col.key];
                const formatted = col.format ? col.format(raw, row) : raw;
                const isNumber = typeof raw === 'number';

                return (
                  <td
                    key={col.key}
                    style={{
                      padding: `var(--table-cell-py) var(--table-cell-px)`,
                      textAlign: col.align ?? (isNumber ? 'right' : 'left'),
                      color: getCellColor(raw),
                      fontVariantNumeric: isNumber ? 'tabular-nums' : undefined,
                      borderBottom:
                        '1px solid var(--color-surface-border)',
                      whiteSpace: 'nowrap',
                      width: col.width,
                    }}
                  >
                    {formatted as ReactNode}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Helpers ───────────────────────────────────────────────── */

function getCellColor(value: unknown): string {
  if (typeof value !== 'number') return 'var(--color-text-primary)';
  if (value > 0) return 'var(--color-signal-positive)';
  if (value < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function SortIndicator({
  active,
  direction,
}: {
  active: boolean;
  direction: SortDir;
}) {
  return (
    <span
      style={{
        fontSize: '8px',
        lineHeight: 1,
        color: active
          ? 'var(--color-accent-primary)'
          : 'var(--color-text-tertiary)',
        display: 'inline-flex',
        flexDirection: 'column',
        gap: '0px',
      }}
    >
      <span style={{ opacity: direction === 'asc' ? 1 : 0.3 }}>{'\u25B2'}</span>
      <span style={{ opacity: direction === 'desc' ? 1 : 0.3 }}>{'\u25BC'}</span>
    </span>
  );
}
