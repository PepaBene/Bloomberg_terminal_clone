import { useState, useCallback, type ReactNode } from 'react';
import clsx from 'clsx';
import { StatementRow, type StatementRowData } from './StatementRow';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type { StatementRowData } from './StatementRow';

export interface StatementTableProps {
  rows: StatementRowData[];
  periods: string[];
  showCommonSize?: boolean;
  commonSizeBase?: number;
  showDelta?: boolean;
  onRowClick?: (row: StatementRowData) => void;
  formatValue?: (value: number | null) => ReactNode;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers: flatten rows with expand/collapse                         */
/* ------------------------------------------------------------------ */

function collectKeys(rows: StatementRowData[]): string[] {
  const keys: string[] = [];
  for (const r of rows) {
    if (r.children && r.children.length > 0) {
      keys.push(r.key);
    }
  }
  return keys;
}

interface FlatRow {
  row: StatementRowData;
  hasChildren: boolean;
}

function flattenRows(
  rows: StatementRowData[],
  expanded: Set<string>,
): FlatRow[] {
  const result: FlatRow[] = [];
  for (const row of rows) {
    const hasChildren = !!(row.children && row.children.length > 0);
    result.push({ row, hasChildren });
    if (hasChildren && expanded.has(row.key)) {
      result.push(...flattenRows(row.children!, expanded));
    }
  }
  return result;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function StatementTable({
  rows,
  periods,
  showCommonSize = false,
  commonSizeBase,
  showDelta = false,
  onRowClick,
  formatValue,
  className,
}: StatementTableProps) {
  /* Start with top-level parent rows expanded */
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(collectKeys(rows)),
  );

  const toggleExpand = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const flatRows = flattenRows(rows, expanded);

  return (
    <div className={clsx('overflow-auto', className)}>
      <table
        className="w-full border-collapse"
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
        }}
      >
        {/* Header row with period columns */}
        <thead>
          <tr>
            <th
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 10,
                padding: `var(--table-cell-py) var(--table-cell-px)`,
                background: 'var(--color-surface-base)',
                borderBottom: '1px solid var(--color-surface-border-strong)',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 500,
                color: 'var(--color-text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                textAlign: 'left',
                minWidth: 180,
              }}
            >
              Line Item
            </th>
            {periods.map((p) => (
              <th
                key={p}
                style={{
                  position: 'sticky',
                  top: 0,
                  zIndex: 10,
                  padding: `var(--table-cell-py) var(--table-cell-px)`,
                  background: 'var(--color-surface-base)',
                  borderBottom: '1px solid var(--color-surface-border-strong)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  color: 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  textAlign: 'right',
                  whiteSpace: 'nowrap',
                  minWidth: 80,
                }}
              >
                {p}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {flatRows.map(({ row, hasChildren }) => (
            <StatementRow
              key={row.key}
              row={row}
              periods={periods}
              isExpanded={expanded.has(row.key)}
              hasChildren={hasChildren}
              onToggle={toggleExpand}
              onRowClick={onRowClick}
              showCommonSize={showCommonSize}
              commonSizeBase={commonSizeBase}
              showDelta={showDelta}
              formatValue={formatValue}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
