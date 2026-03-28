import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  type ReactNode,
  type CSSProperties,
} from 'react';
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
  /** Minimum width for resizable columns (px) */
  minWidth?: number;
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

  /* ── Virtual scrolling ─────────────────────────────────── */
  /** Enable virtual scrolling for large datasets */
  virtualized?: boolean;
  /** Fixed height for virtualized container (default 400) */
  virtualHeight?: number;
  /** Number of buffer rows above/below viewport (default 5) */
  virtualBuffer?: number;

  /* ── Column resizing ───────────────────────────────────── */
  /** Enable column border-drag to resize */
  resizable?: boolean;

  /* ── Row selection ─────────────────────────────────────── */
  /** Enable checkbox row selection */
  selectable?: boolean;
  /** Callback with currently-selected row indices */
  onSelectionChange?: (selectedIndices: number[]) => void;

  /* ── Inline expand ─────────────────────────────────────── */
  /** Enable chevron-expand for each row */
  expandable?: boolean;
  /** Render the expanded content for a given row */
  renderExpanded?: (row: T, index: number) => ReactNode;
}

type SortDir = 'asc' | 'desc' | null;

/* ── Constants ────────────────────────────────────────────── */
const ROW_HEIGHT_PX = 28;
const ROW_HEIGHT_SM_PX = 22;

/* ── Component ────────────────────────────────────────────── */

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  compact = false,
  sortable = false,
  className,
  rowKey,
  virtualized = false,
  virtualHeight = 400,
  virtualBuffer = 5,
  resizable = false,
  selectable = false,
  onSelectionChange,
  expandable = false,
  renderExpanded,
}: DataTableProps<T>) {
  /* ── Sorting state ──────────────────────────────────────── */
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = useCallback(
    (key: string) => {
      if (sortCol === key) {
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

  /* ── Column resizing state ──────────────────────────────── */
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const resizingRef = useRef<{ key: string; startX: number; startW: number } | null>(null);

  const handleResizeStart = useCallback(
    (key: string, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const startW = colWidths[key] ?? 120;
      resizingRef.current = { key, startX: e.clientX, startW };

      const onMove = (ev: MouseEvent) => {
        if (!resizingRef.current) return;
        const delta = ev.clientX - resizingRef.current.startX;
        const col = columns.find((c) => c.key === resizingRef.current!.key);
        const minW = col?.minWidth ?? 40;
        const newW = Math.max(minW, resizingRef.current.startW + delta);
        setColWidths((prev) => ({ ...prev, [resizingRef.current!.key]: newW }));
      };

      const onUp = () => {
        resizingRef.current = null;
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    [colWidths, columns],
  );

  /* ── Row selection state ────────────────────────────────── */
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggleRow = useCallback(
    (idx: number) => {
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(idx)) next.delete(idx);
        else next.add(idx);
        onSelectionChange?.(Array.from(next).sort((a, b) => a - b));
        return next;
      });
    },
    [onSelectionChange],
  );

  const toggleAll = useCallback(() => {
    setSelected((prev) => {
      if (prev.size === data.length) {
        onSelectionChange?.([]);
        return new Set();
      }
      const all = new Set(data.map((_, i) => i));
      onSelectionChange?.(Array.from(all).sort((a, b) => a - b));
      return all;
    });
  }, [data, onSelectionChange]);

  /* ── Inline expand state ────────────────────────────────── */
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleExpand = useCallback((idx: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  /* ── Sorted data ────────────────────────────────────────── */
  const sorted = useMemo(() => {
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
  }, [data, sortCol, sortDir]);

  /* ── Row sizing ─────────────────────────────────────────── */
  const rowHeightNum = compact ? ROW_HEIGHT_SM_PX : ROW_HEIGHT_PX;
  const rowHeight = compact
    ? 'var(--table-row-height-sm)'
    : 'var(--table-row-height)';

  /* ── Virtual scrolling ──────────────────────────────────── */
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const handleScroll = useCallback(() => {
    if (scrollRef.current) setScrollTop(scrollRef.current.scrollTop);
  }, []);

  const totalHeight = sorted.length * rowHeightNum;
  const startIdx = virtualized
    ? Math.max(0, Math.floor(scrollTop / rowHeightNum) - virtualBuffer)
    : 0;
  const endIdx = virtualized
    ? Math.min(
        sorted.length,
        Math.ceil((scrollTop + virtualHeight) / rowHeightNum) + virtualBuffer,
      )
    : sorted.length;
  const visibleRows = sorted.slice(startIdx, endIdx);

  /* ── Effective column list (with selection + expand cols) ── */
  const effectiveColumns = useMemo(() => {
    const cols: Column<T>[] = [];
    if (selectable) {
      cols.push({
        key: '__select__',
        name: '',
        width: '32px',
        sortable: false,
      });
    }
    if (expandable) {
      cols.push({
        key: '__expand__',
        name: '',
        width: '28px',
        sortable: false,
      });
    }
    cols.push(...columns);
    return cols;
  }, [columns, selectable, expandable]);

  /* ── Resolve column width ───────────────────────────────── */
  const getColWidth = useCallback(
    (col: Column<T>): string | undefined => {
      if (col.key === '__select__' || col.key === '__expand__') return col.width;
      if (resizable && colWidths[col.key] != null) return `${colWidths[col.key]}px`;
      return col.width;
    },
    [resizable, colWidths],
  );

  /* ── Init resize widths on mount ────────────────────────── */
  useEffect(() => {
    if (!resizable) return;
    const initial: Record<string, number> = {};
    for (const col of columns) {
      if (colWidths[col.key] == null) {
        initial[col.key] = col.width ? parseInt(col.width, 10) || 120 : 120;
      }
    }
    if (Object.keys(initial).length > 0) {
      setColWidths((prev) => ({ ...initial, ...prev }));
    }
    // Only run on mount / when columns change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resizable, columns]);

  /* ── Render header cell ─────────────────────────────────── */
  const renderHeaderCell = (col: Column<T>) => {
    /* Selection checkbox header */
    if (col.key === '__select__') {
      return (
        <th
          key={col.key}
          className="sticky top-0 z-10"
          style={{
            height: rowHeight,
            padding: `var(--table-cell-py) var(--table-cell-px)`,
            background: 'var(--color-surface-base)',
            borderBottom: '1px solid var(--color-surface-border-strong)',
            width: col.width,
            textAlign: 'center',
          }}
        >
          <input
            type="checkbox"
            checked={selected.size === data.length && data.length > 0}
            onChange={toggleAll}
            style={{ accentColor: 'var(--color-accent-primary)', cursor: 'pointer' }}
          />
        </th>
      );
    }

    /* Expand header — empty */
    if (col.key === '__expand__') {
      return (
        <th
          key={col.key}
          className="sticky top-0 z-10"
          style={{
            height: rowHeight,
            padding: `var(--table-cell-py) var(--table-cell-px)`,
            background: 'var(--color-surface-base)',
            borderBottom: '1px solid var(--color-surface-border-strong)',
            width: col.width,
          }}
        />
      );
    }

    /* Standard header */
    const isSortable = col.sortable !== undefined ? col.sortable : sortable;
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
          width: getColWidth(col),
          position: 'relative',
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
        {resizable && col.key !== '__select__' && col.key !== '__expand__' && (
          <span
            onMouseDown={(e) => handleResizeStart(col.key, e)}
            style={{
              position: 'absolute',
              right: 0,
              top: 0,
              bottom: 0,
              width: '4px',
              cursor: 'col-resize',
              background: 'transparent',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                'var(--color-accent-primary)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = 'transparent';
            }}
          />
        )}
      </th>
    );
  };

  /* ── Render data row ────────────────────────────────────── */
  const renderRow = (row: T, _idx: number, absoluteIdx: number) => {
    const isSelected = selected.has(absoluteIdx);
    const isExpanded = expandedRows.has(absoluteIdx);
    const colSpan = effectiveColumns.length;

    const rowStyle: CSSProperties = virtualized
      ? {
          height: rowHeightNum,
          position: 'absolute',
          top: absoluteIdx * rowHeightNum,
          left: 0,
          right: 0,
          display: 'table-row',
          transition: 'background 0.1s',
        }
      : {
          height: rowHeight,
          transition: 'background 0.1s',
        };

    if (isSelected) {
      rowStyle.background = 'rgba(59,130,246,0.1)';
    }

    const rowEl = (
      <tr
        key={rowKey ? rowKey(row, absoluteIdx) : absoluteIdx}
        className={clsx(onRowClick && 'cursor-pointer')}
        style={rowStyle}
        onClick={onRowClick ? () => onRowClick(row, absoluteIdx) : undefined}
        onMouseEnter={(e) => {
          if (!isSelected) {
            e.currentTarget.style.background = 'var(--color-surface-overlay)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = isSelected
            ? 'rgba(59,130,246,0.1)'
            : 'transparent';
        }}
      >
        {effectiveColumns.map((col) => {
          /* Selection checkbox cell */
          if (col.key === '__select__') {
            return (
              <td
                key={col.key}
                style={{
                  padding: `var(--table-cell-py) var(--table-cell-px)`,
                  borderBottom: '1px solid var(--color-surface-border)',
                  textAlign: 'center',
                  width: col.width,
                }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleRow(absoluteIdx);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  style={{ accentColor: 'var(--color-accent-primary)', cursor: 'pointer' }}
                />
              </td>
            );
          }

          /* Expand chevron cell */
          if (col.key === '__expand__') {
            return (
              <td
                key={col.key}
                style={{
                  padding: `var(--table-cell-py) var(--table-cell-px)`,
                  borderBottom: '1px solid var(--color-surface-border)',
                  textAlign: 'center',
                  width: col.width,
                  cursor: 'pointer',
                  color: 'var(--color-text-tertiary)',
                  userSelect: 'none',
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleExpand(absoluteIdx);
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform var(--transition-fast)',
                    fontSize: '10px',
                  }}
                >
                  {'\u25B6'}
                </span>
              </td>
            );
          }

          /* Standard data cell */
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
                borderBottom: '1px solid var(--color-surface-border)',
                whiteSpace: 'nowrap',
                width: getColWidth(col),
              }}
            >
              {formatted as ReactNode}
            </td>
          );
        })}
      </tr>
    );

    /* Expanded detail row */
    if (expandable && isExpanded && renderExpanded && !virtualized) {
      return (
        <ExpandGroup key={`eg-${rowKey ? rowKey(row, absoluteIdx) : absoluteIdx}`}>
          {rowEl}
          <tr>
            <td
              colSpan={colSpan}
              style={{
                padding: 0,
                borderBottom: '1px solid var(--color-surface-border)',
                background: 'var(--color-surface-raised)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  padding: 'var(--space-3) var(--space-4)',
                  animation: 'expandIn var(--transition-normal) ease-out',
                }}
              >
                {renderExpanded(row, absoluteIdx)}
              </div>
            </td>
          </tr>
        </ExpandGroup>
      );
    }

    return rowEl;
  };

  /* ── Virtualized table ──────────────────────────────────── */
  if (virtualized) {
    return (
      <div
        ref={scrollRef}
        className={clsx('overflow-auto', className)}
        style={{ height: virtualHeight, position: 'relative' }}
        onScroll={handleScroll}
      >
        <table
          className="w-full border-collapse"
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-sm)',
            tableLayout: resizable ? 'fixed' : undefined,
          }}
        >
          <thead>
            <tr>{effectiveColumns.map(renderHeaderCell)}</tr>
          </thead>
        </table>
        <div style={{ height: totalHeight, position: 'relative' }}>
          <table
            className="w-full border-collapse"
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              tableLayout: resizable ? 'fixed' : undefined,
            }}
          >
            <tbody>
              {visibleRows.map((row, i) => {
                const absoluteIdx = startIdx + i;
                return renderRow(row, i, absoluteIdx);
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  /* ── Standard table ─────────────────────────────────────── */
  return (
    <div className={clsx('overflow-auto', className)}>
      <style>{expandKeyframes}</style>
      <table
        className="w-full border-collapse"
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
          tableLayout: resizable ? 'fixed' : undefined,
        }}
      >
        <thead>
          <tr>{effectiveColumns.map(renderHeaderCell)}</tr>
        </thead>
        <tbody>
          {sorted.map((row, idx) => renderRow(row, idx, idx))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Expand animation keyframes ───────────────────────────── */

const expandKeyframes = `
@keyframes expandIn {
  from { max-height: 0; opacity: 0; }
  to { max-height: 500px; opacity: 1; }
}
`;

/* ── ExpandGroup: fragments for adjacent rows ─────────────── */

function ExpandGroup({ children }: { children: ReactNode }) {
  return <>{children}</>;
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
