import { useMemo } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import type { Column } from '@/components/ui/DataTable';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ScreenResultColumn {
  key: string;
  label: string;
  format?: string;
}

export interface ScreenResultsProps {
  results: Record<string, unknown>[];
  columns: ScreenResultColumn[];
  onRowClick?: (row: Record<string, unknown>) => void;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function signalColor(value: unknown): string | undefined {
  if (typeof value !== 'number') return undefined;
  if (value > 0) return 'var(--color-signal-positive)';
  if (value < 0) return 'var(--color-signal-negative)';
  return undefined;
}

function formatValue(value: unknown, format?: string): string {
  if (value == null) return '\u2014';
  if (typeof value !== 'number') return String(value);

  switch (format) {
    case 'pct':
      return `${value.toFixed(1)}%`;
    case 'currency':
      if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
      if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
      return `$${value.toFixed(2)}`;
    case 'multiple':
      return `${value.toFixed(1)}x`;
    default:
      return value.toLocaleString();
  }
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ScreenResults({ results, columns, onRowClick }: ScreenResultsProps) {
  /* Map ScreenResultColumn to DataTable Column */
  const tableColumns = useMemo<Column<Record<string, unknown>>[]>(
    () =>
      columns.map((col) => ({
        key: col.key,
        name: col.label,
        align: 'right' as const,
        sortable: true,
        format: (value: unknown) => {
          const formatted = formatValue(value, col.format);
          const color = typeof value === 'number' ? signalColor(value) : undefined;
          if (color) {
            return (
              <span style={{ color, fontVariantNumeric: 'tabular-nums' }}>
                {formatted}
              </span>
            );
          }
          return formatted;
        },
      })),
    [columns],
  );

  /* Override first column to be left-aligned (typically company name/ticker) */
  const adjustedColumns = useMemo(() => {
    if (tableColumns.length === 0) return tableColumns;
    const first = tableColumns[0];
    if (!first) return tableColumns;
    return [{ ...first, align: 'left' as const }, ...tableColumns.slice(1)];
  }, [tableColumns]);

  const handleRowClick = useMemo(() => {
    if (!onRowClick) return undefined;
    return (row: Record<string, unknown>) => onRowClick(row);
  }, [onRowClick]);

  return (
    <div className="terminal-panel flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Screen Results
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {results.length} {results.length === 1 ? 'result' : 'results'}
        </span>
      </div>

      {/* Table */}
      {results.length > 0 ? (
        <DataTable
          columns={adjustedColumns}
          data={results}
          sortable
          compact
          onRowClick={handleRowClick}
        />
      ) : (
        <div
          style={{
            padding: '24px 0',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          No results match the current screen criteria
        </div>
      )}
    </div>
  );
}
