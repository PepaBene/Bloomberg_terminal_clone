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

  // [Bug 98 fix] — Parse to number safely; API may return string representations
  let numValue: number;
  if (typeof value === 'number') {
    numValue = value;
  } else if (typeof value === 'string' && format) {
    const parsed = parseFloat(value);
    if (isNaN(parsed)) return String(value);
    numValue = parsed;
  } else {
    return String(value);
  }

  switch (format) {
    case 'pct':
    case 'percent':
      return `${numValue.toFixed(1)}%`;
    case 'currency':
      if (Math.abs(numValue) >= 1e9) return `$${(numValue / 1e9).toFixed(1)}B`;
      if (Math.abs(numValue) >= 1e6) return `$${(numValue / 1e6).toFixed(1)}M`;
      return `$${numValue.toFixed(2)}`;
    case 'multiple':
      return `${numValue.toFixed(1)}x`;
    case 'number':
      return numValue.toLocaleString();
    default:
      return numValue.toLocaleString();
  }
}

/** Format negative numbers with minus sign, never parentheses */
function formatNumericDisplay(value: unknown, format?: string): string {
  const formatted = formatValue(value, format);
  // Ensure no parenthesized negatives sneak through from toLocaleString
  return formatted.replace(/\(([^)]+)\)/, '-$1');
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
          const formatted = formatNumericDisplay(value, col.format);
          const color = typeof value === 'number' ? signalColor(value) : undefined;
          if (color) {
            return (
              <span
                style={{
                  color,
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatted}
              </span>
            );
          }
          return (
            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {formatted}
            </span>
          );
        },
      })),
    [columns],
  );

  /* Override first column to be left-aligned (typically company name/ticker) */
  const adjustedColumns = useMemo(() => {
    if (tableColumns.length === 0) return tableColumns;
    const first = tableColumns[0];
    if (!first) return tableColumns;
    return [
      {
        ...first,
        align: 'left' as const,
        format: (value: unknown) => (
          <span style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-text-primary)' }}>
            {String(value ?? '\u2014')}
          </span>
        ),
      },
      ...tableColumns.slice(1),
    ];
  }, [tableColumns]);

  const handleRowClick = useMemo(() => {
    if (!onRowClick) return undefined;
    return (row: Record<string, unknown>) => onRowClick(row);
  }, [onRowClick]);

  return (
    <div className="terminal-panel animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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
            padding: 'var(--space-6) 0',
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
