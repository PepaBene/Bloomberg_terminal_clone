import { useCallback, type ReactNode } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface StatementRowData {
  key: string;
  label: string;
  indent: number;
  isHeader?: boolean;
  isBold?: boolean;
  values: (number | null)[];
  children?: StatementRowData[];
}

export interface StatementRowProps {
  row: StatementRowData;
  periods: string[];
  isExpanded: boolean;
  hasChildren: boolean;
  onToggle: (key: string) => void;
  onRowClick?: (row: StatementRowData) => void;
  showCommonSize?: boolean;
  commonSizeBase?: number;
  showDelta?: boolean;
  formatValue?: (value: number | null) => ReactNode;
  /** YoY change threshold (0-1) above which a cell is highlighted as anomalous. Default 0.3 = 30%. */
  anomalyThreshold?: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const INDENT_PX = 12;

function defaultFormat(value: number | null): ReactNode {
  if (value == null) return '\u2014';
  // Format large numbers in millions
  if (Math.abs(value) >= 1e6) {
    const inM = value / 1e6;
    return `${inM >= 0 ? '' : '('}${Math.abs(inM).toFixed(1)}${inM < 0 ? ')' : ''}`;
  }
  if (Math.abs(value) >= 1e3) {
    return value.toLocaleString();
  }
  return value.toFixed(1);
}

function valueColor(value: number | null): string {
  if (value == null) return 'var(--color-text-tertiary)';
  if (value < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function deltaValue(current: number | null, prior: number | null): number | null {
  if (current == null || prior == null || prior === 0) return null;
  return ((current - prior) / Math.abs(prior)) * 100;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function StatementRow({
  row,
  periods: _periods,
  isExpanded,
  hasChildren,
  onToggle,
  onRowClick,
  showCommonSize = false,
  commonSizeBase,
  showDelta = false,
  formatValue,
  anomalyThreshold,
}: StatementRowProps) {
  const fmt = formatValue ?? defaultFormat;

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onToggle(row.key);
    },
    [onToggle, row.key],
  );

  const handleClick = useCallback(() => {
    onRowClick?.(row);
  }, [onRowClick, row]);

  const isHeader = row.isHeader ?? false;
  const isBold = row.isBold ?? isHeader;

  return (
    <tr
      className={clsx(onRowClick && !isHeader && 'cursor-pointer')}
      onClick={!isHeader ? handleClick : undefined}
      onMouseEnter={(e) => {
        if (!isHeader) {
          e.currentTarget.style.background = 'var(--color-surface-overlay)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isHeader
          ? 'var(--color-surface-overlay)'
          : 'transparent';
      }}
      style={{
        background: isHeader ? 'var(--color-surface-overlay)' : 'transparent',
        transition: 'background var(--transition-fast)',
      }}
    >
      {/* Label cell with indent and expand/collapse */}
      <td
        style={{
          padding: `var(--table-cell-py) var(--table-cell-px)`,
          paddingLeft: `${8 + row.indent * INDENT_PX}px`,
          borderBottom: '1px solid var(--color-surface-border)',
          fontFamily: 'var(--font-ui)',
          fontWeight: isBold ? 600 : 400,
          color: isHeader ? 'var(--color-text-primary)' : 'var(--color-text-primary)',
          fontSize: 'var(--text-sm)',
          whiteSpace: 'nowrap',
        }}
      >
        <span className="inline-flex items-center gap-1">
          {hasChildren && (
            <span
              onClick={handleToggle}
              style={{
                display: 'inline-block',
                transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform var(--transition-fast)',
                fontSize: '8px',
                color: 'var(--color-text-tertiary)',
                cursor: 'pointer',
                marginRight: '4px',
                userSelect: 'none',
              }}
            >
              {'\u25B6'}
            </span>
          )}
          {row.label}
        </span>
      </td>

      {/* Value cells */}
      {row.values.map((val, i) => {
        // Common-size percentage
        const commonSizePct =
          showCommonSize && commonSizeBase && val != null
            ? ((val / commonSizeBase) * 100).toFixed(1) + '%'
            : null;

        // Delta (QoQ / YoY change)
        const delta = showDelta && i < row.values.length - 1
          ? deltaValue(val, row.values[i + 1] ?? null)
          : null;

        // Anomaly detection: check if YoY change exceeds threshold
        const yoyChange = i < row.values.length - 1
          ? deltaValue(val, row.values[i + 1] ?? null)
          : null;
        const isAnomaly =
          anomalyThreshold != null &&
          yoyChange != null &&
          Math.abs(yoyChange) > anomalyThreshold * 100;
        const anomalyPositive = isAnomaly && yoyChange != null && yoyChange > 0;

        return (
          <td
            key={i}
            style={{
              padding: `var(--table-cell-py) var(--table-cell-px)`,
              textAlign: 'right',
              borderBottom: '1px solid var(--color-surface-border)',
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              fontSize: 'var(--text-sm)',
              fontWeight: isBold ? 600 : 400,
              color: valueColor(val),
              whiteSpace: 'nowrap',
              background: isAnomaly
                ? anomalyPositive
                  ? 'rgba(45, 184, 125, 0.10)'
                  : 'rgba(224, 82, 82, 0.10)'
                : undefined,
            }}
          >
            <span>
              {fmt(val)}
              {isAnomaly && (
                <span
                  style={{ marginLeft: '4px', fontSize: 'var(--text-xs)' }}
                  title={`YoY change: ${yoyChange != null && yoyChange > 0 ? '+' : ''}${yoyChange?.toFixed(1)}%`}
                >
                  &#9888;
                </span>
              )}
            </span>
            {commonSizePct && (
              <span
                style={{
                  display: 'block',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                {commonSizePct}
              </span>
            )}
            {delta != null && (
              <span
                style={{
                  display: 'block',
                  fontSize: 'var(--text-xs)',
                  color:
                    delta > 0
                      ? 'var(--color-signal-positive)'
                      : delta < 0
                        ? 'var(--color-signal-negative)'
                        : 'var(--color-text-tertiary)',
                }}
              >
                {delta > 0 ? '+' : ''}
                {delta.toFixed(1)}%
              </span>
            )}
          </td>
        );
      })}
    </tr>
  );
}
