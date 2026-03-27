import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import clsx from 'clsx';

/* ── Types ────────────────────────────────────────────────── */

export interface CommandResult {
  id: string;
  /** Primary label (e.g. ticker symbol) */
  title: string;
  /** Secondary label (e.g. company name) */
  subtitle?: string;
  /** Tertiary metadata (e.g. "NYSE", "$2.4T") */
  meta?: string;
  /** Result group key */
  group: string;
}

export interface CommandBarProps {
  /** Whether the command bar is open */
  open: boolean;
  /** Close callback */
  onClose: () => void;
  /** Called when user submits a query string */
  onSearch?: (query: string) => void;
  /** Called when a result item is selected */
  onSelect?: (result: CommandResult) => void;
  /** Results to display, grouped by `group` field */
  results?: CommandResult[];
  /** Placeholder text */
  placeholder?: string;
  /** Additional CSS class for the overlay */
  className?: string;
}

/* ── Component ────────────────────────────────────────────── */

export function CommandBar({
  open,
  onClose,
  onSearch,
  onSelect,
  results = [],
  placeholder = 'Search securities, commands\u2026',
  className,
}: CommandBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      // Delay focus to ensure DOM is ready
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Global keyboard listener for Ctrl+K / Escape
  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (!open) onClose(); // toggle — parent should flip `open`
      }
      if (e.key === '/' && !open) {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
        e.preventDefault();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Group results
  const groups = groupResults(results);
  const flatResults = results;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((prev) => Math.min(prev + 1, flatResults.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const selected = flatResults[activeIdx];
        if (selected) onSelect?.(selected);
        else onSearch?.(query);
        return;
      }
    },
    [activeIdx, flatResults, onClose, onSearch, onSelect, query],
  );

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className={clsx('fixed inset-0 z-[100] flex justify-center', className)}
      style={{ background: 'rgba(0, 0, 0, 0.6)' }}
      onClick={onClose}
    >
      {/* Dialog */}
      <div
        className="flex w-full max-w-2xl flex-col overflow-hidden rounded-[var(--border-radius-lg,6px)]"
        style={{
          marginTop: '80px',
          maxHeight: '480px',
          background: 'var(--color-surface-raised)',
          border: '1px solid var(--color-surface-border)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-2 px-4"
          style={{
            height: '48px',
            borderBottom: '1px solid var(--color-surface-border)',
          }}
        >
          <SearchIcon />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIdx(0);
              onSearch?.(e.target.value);
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 border-none bg-transparent outline-none"
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-md)',
              color: 'var(--color-text-primary)',
            }}
          />
          <kbd
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              padding: '2px 6px',
              borderRadius: '3px',
              border: '1px solid var(--color-surface-border-strong)',
            }}
          >
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto" style={{ padding: '4px 0' }}>
          {groups.length === 0 && query.length > 0 && (
            <div
              className="px-4 py-6 text-center"
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-tertiary)',
              }}
            >
              No results found
            </div>
          )}

          {groups.map(([groupName, items]) => (
            <div key={groupName}>
              {/* Group header */}
              <div
                className="px-4 py-1"
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {groupName}
              </div>
              {/* Group items */}
              {items.map((result) => {
                const globalIdx = flatResults.indexOf(result);
                const isActive = globalIdx === activeIdx;

                return (
                  <div
                    key={result.id}
                    className="flex cursor-pointer items-center gap-3 px-4"
                    style={{
                      height: '36px',
                      background: isActive
                        ? 'var(--color-surface-overlay)'
                        : 'transparent',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={() => setActiveIdx(globalIdx)}
                    onClick={() => onSelect?.(result)}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--color-accent-primary)',
                        fontWeight: 600,
                        minWidth: '56px',
                      }}
                    >
                      {result.title}
                    </span>
                    {result.subtitle && (
                      <span
                        className="min-w-0 flex-1 truncate"
                        style={{
                          fontFamily: 'var(--font-ui)',
                          fontSize: 'var(--text-sm)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {result.subtitle}
                      </span>
                    )}
                    {result.meta && (
                      <span
                        style={{
                          fontFamily: 'var(--font-data)',
                          fontSize: 'var(--text-xs)',
                          color: 'var(--color-text-tertiary)',
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {result.meta}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div
          className="flex items-center gap-4 border-t px-4"
          style={{
            height: '32px',
            borderColor: 'var(--color-surface-border)',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          <span>
            <kbd className="font-data">{'↑↓'}</kbd> navigate
          </span>
          <span>
            <kbd className="font-data">{'↵'}</kbd> select
          </span>
          <span>
            <kbd className="font-data">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Helpers ───────────────────────────────────────────────── */

function groupResults(results: CommandResult[]): [string, CommandResult[]][] {
  const map = new Map<string, CommandResult[]>();
  for (const r of results) {
    const existing = map.get(r.group);
    if (existing) {
      existing.push(r);
    } else {
      map.set(r.group, [r]);
    }
  }
  return Array.from(map.entries());
}

function SearchIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      style={{ flexShrink: 0 }}
    >
      <circle
        cx="7"
        cy="7"
        r="5.5"
        stroke="var(--color-text-tertiary)"
        strokeWidth="1.5"
      />
      <line
        x1="11.5"
        y1="11.5"
        x2="14.5"
        y2="14.5"
        stroke="var(--color-text-tertiary)"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
