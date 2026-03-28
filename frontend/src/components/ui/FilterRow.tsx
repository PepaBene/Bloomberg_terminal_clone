import { useCallback } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface FilterRowColumn {
  key: string;
  type: 'text' | 'number' | 'select';
  options?: string[];
}

export interface FilterRowProps {
  columns: FilterRowColumn[];
  filters: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onClear: () => void;
}

/* ── Component ────────────────────────────────────────────── */

export function FilterRow({ columns, filters, onChange, onClear }: FilterRowProps) {
  const hasActiveFilters = Object.values(filters).some((v) => v.length > 0);

  return (
    <tr
      style={{
        background: 'var(--color-surface-overlay)',
      }}
    >
      {columns.map((col) => (
        <td
          key={col.key}
          style={{
            padding: '2px 4px',
            borderBottom: '1px solid var(--color-surface-border)',
          }}
        >
          <FilterInput
            column={col}
            value={filters[col.key] ?? ''}
            onChange={onChange}
          />
        </td>
      ))}

      {/* Clear all button cell */}
      <td
        style={{
          padding: '2px 4px',
          borderBottom: '1px solid var(--color-surface-border)',
          textAlign: 'right',
          whiteSpace: 'nowrap',
        }}
      >
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onClear}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '2px 6px',
              borderRadius: 'var(--border-radius-sm, 3px)',
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-tertiary)';
            }}
          >
            Clear
          </button>
        )}
      </td>
    </tr>
  );
}

/* ── FilterInput per column type ─────────────────────────── */

const INPUT_STYLE: React.CSSProperties = {
  width: '100%',
  height: '24px',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  color: 'var(--color-text-primary)',
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: 'var(--border-radius-sm, 3px)',
  padding: '0 6px',
  outline: 'none',
  boxSizing: 'border-box',
};

function FilterInput({
  column,
  value,
  onChange,
}: {
  column: FilterRowColumn;
  value: string;
  onChange: (key: string, value: string) => void;
}) {
  const handleChange = useCallback(
    (v: string) => onChange(column.key, v),
    [column.key, onChange],
  );

  if (column.type === 'select') {
    return (
      <select
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        style={INPUT_STYLE}
      >
        <option value="">All</option>
        {column.options?.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  if (column.type === 'number') {
    return (
      <input
        type="text"
        inputMode="numeric"
        placeholder="min-max"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        style={INPUT_STYLE}
      />
    );
  }

  /* Default: text with search icon */
  return (
    <div style={{ position: 'relative' }}>
      <span
        style={{
          position: 'absolute',
          left: '4px',
          top: '50%',
          transform: 'translateY(-50%)',
          pointerEvents: 'none',
          color: 'var(--color-text-tertiary)',
          display: 'flex',
        }}
      >
        <SearchMiniIcon />
      </span>
      <input
        type="text"
        placeholder="Filter\u2026"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        style={{
          ...INPUT_STYLE,
          paddingLeft: '20px',
        }}
      />
    </div>
  );
}

/* ── Icons ────────────────────────────────────────────────── */

function SearchMiniIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <circle
        cx="5.25"
        cy="5.25"
        r="3.75"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <line
        x1="8"
        y1="8"
        x2="10.5"
        y2="10.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}
