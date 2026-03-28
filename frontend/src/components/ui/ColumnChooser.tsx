import { useState, useRef, useEffect, useCallback } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface ColumnChooserColumn {
  key: string;
  name: string;
  visible: boolean;
}

export interface ColumnChooserProps {
  columns: ColumnChooserColumn[];
  onChange: (key: string, visible: boolean) => void;
  onReset?: () => void;
}

/* ── Component ────────────────────────────────────────────── */

export function ColumnChooser({ columns, onChange, onReset }: ColumnChooserProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  /* Close on outside click */
  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (
      panelRef.current &&
      !panelRef.current.contains(e.target as Node) &&
      buttonRef.current &&
      !buttonRef.current.contains(e.target as Node)
    ) {
      setOpen(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open, handleClickOutside]);

  /* Close on Escape */
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  const allVisible = columns.every((c) => c.visible);

  const handleShowAll = () => {
    for (const col of columns) {
      if (!col.visible) onChange(col.key, true);
    }
  };

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      {/* Trigger button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Choose columns"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '28px',
          height: '28px',
          border: '1px solid var(--color-surface-border)',
          borderRadius: 'var(--border-radius-sm, 4px)',
          background: open
            ? 'var(--color-surface-overlay)'
            : 'var(--color-surface-raised)',
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
          transition: 'background 0.15s',
        }}
      >
        <GridIcon />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          ref={panelRef}
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '200px',
            maxHeight: '320px',
            overflowY: 'auto',
            background: 'var(--color-surface-raised)',
            border: '1px solid var(--color-surface-border)',
            borderRadius: 'var(--border-radius-md, 6px)',
            boxShadow: 'var(--shadow-float, 0 4px 24px rgba(0,0,0,0.65))',
            zIndex: 50,
            padding: '4px 0',
          }}
        >
          {/* Column list */}
          {columns.map((col) => (
            <label
              key={col.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 12px',
                cursor: 'pointer',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-secondary)',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-surface-overlay)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <input
                type="checkbox"
                checked={col.visible}
                onChange={() => onChange(col.key, !col.visible)}
                style={{
                  accentColor: 'var(--color-accent-primary)',
                  cursor: 'pointer',
                  margin: 0,
                }}
              />
              {col.name}
            </label>
          ))}

          {/* Footer actions */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              padding: '6px 12px 4px',
              borderTop: '1px solid var(--color-surface-border)',
              marginTop: '4px',
            }}
          >
            {!allVisible && (
              <button
                type="button"
                onClick={handleShowAll}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-accent-primary)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                Show All
              </button>
            )}
            {onReset && (
              <button
                type="button"
                onClick={() => {
                  onReset();
                  setOpen(false);
                }}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  marginLeft: 'auto',
                }}
              >
                Reset
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Icons ────────────────────────────────────────────────── */

function GridIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
    >
      <rect x="1" y="1" width="5" height="5" rx="0.5" />
      <rect x="8" y="1" width="5" height="5" rx="0.5" />
      <rect x="1" y="8" width="5" height="5" rx="0.5" />
      <rect x="8" y="8" width="5" height="5" rx="0.5" />
    </svg>
  );
}
