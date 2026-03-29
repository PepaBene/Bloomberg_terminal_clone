import { useState, useCallback, useMemo } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MetricItem {
  key: string;
  label: string;
  description?: string;
}

export interface MetricCategory {
  name: string;
  metrics: MetricItem[];
}

export interface MetricCategoryTreeProps {
  categories: MetricCategory[];
  onSelect: (key: string) => void;
  selected?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function MetricCategoryTree({ categories, onSelect, selected }: MetricCategoryTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');

  const toggleCategory = useCallback((name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  /* Filter categories/metrics by search */
  const filtered = useMemo(() => {
    if (!search.trim()) return categories;
    const q = search.toLowerCase();
    return categories
      .map((cat) => ({
        ...cat,
        metrics: cat.metrics.filter(
          (m) =>
            m.label.toLowerCase().includes(q) ||
            m.key.toLowerCase().includes(q) ||
            (m.description?.toLowerCase().includes(q) ?? false),
        ),
      }))
      .filter((cat) => cat.metrics.length > 0);
  }, [categories, search]);

  return (
    <div className="terminal-panel flex flex-col gap-2" style={{ maxHeight: 400, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
        Metrics
      </div>

      {/* Search filter */}
      <input
        type="text"
        placeholder="Search metrics\u2026"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          background: 'var(--color-surface-base)',
          color: 'var(--color-text-primary)',
          border: '1px solid var(--color-surface-border)',
          borderRadius: 3,
          padding: '5px 8px',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          outline: 'none',
          width: '100%',
        }}
      />

      {/* Category tree */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {filtered.map((cat) => {
          const isExpanded = expanded.has(cat.name) || search.trim().length > 0;

          return (
            <div key={cat.name} style={{ marginBottom: 2 }}>
              {/* Category header */}
              <button
                type="button"
                onClick={() => toggleCategory(cat.name)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'none',
                  border: 'none',
                  padding: '4px 2px',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  textAlign: 'left',
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: 8,
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform var(--transition-fast)',
                    color: 'var(--color-text-tertiary)',
                  }}
                >
                  {'\u25B6'}
                </span>
                {cat.name}
                <span
                  style={{
                    fontWeight: 400,
                    color: 'var(--color-text-tertiary)',
                    marginLeft: 'auto',
                    fontSize: 'var(--text-xs)',
                    fontFamily: 'var(--font-data)',
                  }}
                >
                  {cat.metrics.length}
                </span>
              </button>

              {/* Metrics */}
              {isExpanded && (
                <div style={{ paddingLeft: 14 }}>
                  {cat.metrics.map((m) => {
                    const isSelected = selected === m.key;

                    return (
                      <button
                        key={m.key}
                        type="button"
                        onClick={() => onSelect(m.key)}
                        style={{
                          width: '100%',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                          background: isSelected
                            ? 'rgba(59, 130, 246, 0.12)'
                            : 'transparent',
                          border: 'none',
                          borderRadius: 3,
                          padding: '3px 6px',
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'background var(--transition-fast)',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected)
                            e.currentTarget.style.background = 'var(--color-surface-overlay)';
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected)
                            e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        <span
                          style={{
                            fontFamily: 'var(--font-ui)',
                            fontSize: 'var(--text-xs)',
                            color: isSelected
                              ? 'var(--color-accent-primary)'
                              : 'var(--color-text-primary)',
                            fontWeight: isSelected ? 600 : 400,
                          }}
                        >
                          {m.label}
                        </span>
                        {m.description && (
                          <span
                            style={{
                              fontFamily: 'var(--font-ui)',
                              fontSize: 10,
                              color: 'var(--color-text-tertiary)',
                              lineHeight: 1.3,
                            }}
                          >
                            {m.description}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              padding: '12px 4px',
              textAlign: 'center',
            }}
          >
            No metrics match &ldquo;{search}&rdquo;
          </div>
        )}
      </div>
    </div>
  );
}
