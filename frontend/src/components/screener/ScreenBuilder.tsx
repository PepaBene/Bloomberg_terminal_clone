import { useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ScreenFilter {
  id: string;
  metric: string;
  operator: '>' | '<' | '=' | 'between';
  value: number;
  valueTo?: number;
}

export interface MetricDef {
  key: string;
  label: string;
  category?: string;
}

export interface ScreenBuilderProps {
  filters: ScreenFilter[];
  onChange: (filters: ScreenFilter[]) => void;
  availableMetrics: MetricDef[];
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const OPERATORS: { value: ScreenFilter['operator']; label: string }[] = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '=', label: '=' },
  { value: 'between', label: 'Between' },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ScreenBuilder({ filters, onChange, availableMetrics }: ScreenBuilderProps) {
  const handleMetricChange = useCallback(
    (id: string, metric: string) => {
      onChange(filters.map((f) => (f.id === id ? { ...f, metric } : f)));
    },
    [filters, onChange],
  );

  const handleOperatorChange = useCallback(
    (id: string, operator: ScreenFilter['operator']) => {
      onChange(filters.map((f) => (f.id === id ? { ...f, operator } : f)));
    },
    [filters, onChange],
  );

  const handleValueChange = useCallback(
    (id: string, value: number) => {
      onChange(filters.map((f) => (f.id === id ? { ...f, value } : f)));
    },
    [filters, onChange],
  );

  const handleValueToChange = useCallback(
    (id: string, valueTo: number) => {
      onChange(filters.map((f) => (f.id === id ? { ...f, valueTo } : f)));
    },
    [filters, onChange],
  );

  const handleRemove = useCallback(
    (id: string) => {
      onChange(filters.filter((f) => f.id !== id));
    },
    [filters, onChange],
  );

  const handleAdd = useCallback(() => {
    const newId = `filter-${Date.now()}`;
    const firstMetric = availableMetrics[0]?.key ?? '';
    onChange([
      ...filters,
      { id: newId, metric: firstMetric, operator: '>', value: 0 },
    ]);
  }, [filters, onChange, availableMetrics]);

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
        Screen Builder
      </div>

      {/* Filter rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filters.map((filter) => (
          <div
            key={filter.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 8px',
              background: 'var(--color-surface-raised)',
              borderRadius: 4,
              border: '1px solid var(--color-surface-border)',
            }}
          >
            {/* Metric dropdown */}
            <select
              value={filter.metric}
              onChange={(e) => handleMetricChange(filter.id, e.target.value)}
              style={{
                flex: 2,
                minWidth: 120,
                background: 'var(--color-surface-base)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-surface-border)',
                borderRadius: 3,
                padding: '4px 8px',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                outline: 'none',
              }}
            >
              {availableMetrics.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>

            {/* Operator dropdown */}
            <select
              value={filter.operator}
              onChange={(e) =>
                handleOperatorChange(filter.id, e.target.value as ScreenFilter['operator'])
              }
              style={{
                width: 90,
                background: 'var(--color-surface-base)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-surface-border)',
                borderRadius: 3,
                padding: '4px 8px',
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                outline: 'none',
              }}
            >
              {OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>

            {/* Value input */}
            <input
              type="number"
              value={filter.value}
              onChange={(e) => handleValueChange(filter.id, parseFloat(e.target.value) || 0)}
              style={{
                width: 80,
                background: 'var(--color-surface-base)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-surface-border)',
                borderRadius: 3,
                padding: '4px 8px',
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                fontVariantNumeric: 'tabular-nums',
                outline: 'none',
              }}
            />

            {/* Second value for "between" */}
            {filter.operator === 'between' && (
              <>
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-tertiary)',
                  }}
                >
                  and
                </span>
                <input
                  type="number"
                  value={filter.valueTo ?? 0}
                  onChange={(e) =>
                    handleValueToChange(filter.id, parseFloat(e.target.value) || 0)
                  }
                  style={{
                    width: 80,
                    background: 'var(--color-surface-base)',
                    color: 'var(--color-text-primary)',
                    border: '1px solid var(--color-surface-border)',
                    borderRadius: 3,
                    padding: '4px 8px',
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontVariantNumeric: 'tabular-nums',
                    outline: 'none',
                  }}
                />
              </>
            )}

            {/* Remove button */}
            <button
              type="button"
              onClick={() => handleRemove(filter.id)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-text-tertiary)',
                cursor: 'pointer',
                fontSize: 14,
                lineHeight: 1,
                padding: '2px 4px',
                flexShrink: 0,
              }}
              title="Remove filter"
              aria-label={`Remove filter ${filter.metric}`}
            >
              {'\u2715'}
            </button>
          </div>
        ))}
      </div>

      {/* Add Filter button */}
      <button
        type="button"
        onClick={handleAdd}
        style={{
          alignSelf: 'flex-start',
          background: 'var(--color-surface-raised)',
          color: 'var(--color-accent-primary)',
          border: '1px solid var(--color-surface-border)',
          borderRadius: 4,
          padding: '6px 14px',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
          cursor: 'pointer',
          letterSpacing: '0.02em',
          transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--color-surface-overlay)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'var(--color-surface-raised)';
        }}
      >
        + Add Filter
      </button>
    </div>
  );
}
