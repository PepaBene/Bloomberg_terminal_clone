import { useEffect, useRef, useCallback } from 'react';
import type { ShortcutEntry } from '@/hooks/useKeyboardShortcuts';

/* ── Types ────────────────────────────────────────────────── */

export interface ShortcutReferenceProps {
  open: boolean;
  onClose: () => void;
  shortcuts: ShortcutEntry[];
}

/* ── Helpers ──────────────────────────────────────────────── */

/** Group shortcuts by category, preserving insertion order. */
function groupByCategory(shortcuts: ShortcutEntry[]): [string, ShortcutEntry[]][] {
  const map = new Map<string, ShortcutEntry[]>();
  for (const s of shortcuts) {
    const existing = map.get(s.category);
    if (existing) {
      existing.push(s);
    } else {
      map.set(s.category, [s]);
    }
  }
  return Array.from(map.entries());
}

/** Format a shortcut key definition into human-readable key badges. */
function formatKeys(entry: ShortcutEntry): string[] {
  const parts: string[] = [];
  if (entry.ctrl || entry.meta) parts.push('Ctrl');
  if (entry.shift) parts.push('Shift');
  parts.push(prettyKey(entry.key));
  return parts;
}

function prettyKey(key: string): string {
  const map: Record<string, string> = {
    arrowup: '\u2191',
    arrowdown: '\u2193',
    arrowleft: '\u2190',
    arrowright: '\u2192',
    escape: 'Esc',
    enter: '\u21B5',
    tab: 'Tab',
    '/': '/',
    '?': '?',
  };
  return map[key.toLowerCase()] ?? key.toUpperCase();
}

/* ── Styles ───────────────────────────────────────────────── */

const kbdStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '22px',
  height: '22px',
  padding: '0 6px',
  borderRadius: '4px',
  border: '1px solid var(--color-surface-border-strong)',
  background: 'var(--color-surface-raised)',
  fontFamily: 'var(--font-data)',
  fontSize: '11px',
  lineHeight: 1,
  color: 'var(--color-text-secondary)',
  boxShadow: '0 1px 0 var(--color-surface-border)',
  whiteSpace: 'nowrap',
};

/* ── Component ────────────────────────────────────────────── */

export function ShortcutReference({ open, onClose, shortcuts }: ShortcutReferenceProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    },
    [open, onClose],
  );

  useEffect(() => {
    if (!open) return;
    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [open, handleKeyDown]);

  if (!open) return null;

  const groups = groupByCategory(shortcuts);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[200] flex items-center justify-center"
      style={{
        background: 'rgba(6, 8, 9, 0.85)',
        animation: 'shortcutFadeIn 150ms ease-out both',
      }}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      {/* Dialog */}
      <div
        className="flex flex-col overflow-hidden rounded-lg"
        style={{
          width: '640px',
          maxWidth: '90vw',
          maxHeight: '80vh',
          background: 'var(--color-surface-raised)',
          border: '1px solid var(--color-surface-border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
        }}
      >
        {/* Header */}
        <div
          className="flex shrink-0 items-center justify-between px-6"
          style={{
            height: '48px',
            borderBottom: '1px solid var(--color-surface-border)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-lg)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
            }}
          >
            Keyboard Shortcuts
          </span>
          <kbd style={{ ...kbdStyle, fontSize: '10px', height: '20px', minWidth: '18px' }}>
            Esc
          </kbd>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-4" style={{ gap: '24px', display: 'flex', flexDirection: 'column' }}>
          {groups.map(([category, items]) => (
            <div key={category}>
              {/* Category header */}
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: 'var(--color-text-tertiary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: '8px',
                  paddingBottom: '4px',
                  borderBottom: '1px solid var(--color-surface-border)',
                }}
              >
                {category}
              </div>

              {/* Shortcut rows */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {items.map((entry, i) => {
                  const keys = formatKeys(entry);
                  return (
                    <div
                      key={`${category}-${i}`}
                      className="flex items-center justify-between rounded px-2"
                      style={{
                        height: '32px',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'var(--color-surface-overlay)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      {/* Description */}
                      <span
                        style={{
                          fontFamily: 'var(--font-ui)',
                          fontSize: 'var(--text-sm)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {entry.description}
                      </span>

                      {/* Key badges */}
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        {keys.map((k, ki) => (
                          <span key={ki} style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            {ki > 0 && (
                              <span
                                style={{
                                  fontFamily: 'var(--font-data)',
                                  fontSize: '9px',
                                  color: 'var(--color-text-tertiary)',
                                }}
                              >
                                +
                              </span>
                            )}
                            <kbd style={kbdStyle}>{k}</kbd>
                          </span>
                        ))}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          className="flex shrink-0 items-center justify-center px-6"
          style={{
            height: '36px',
            borderTop: '1px solid var(--color-surface-border)',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          Press <kbd style={{ ...kbdStyle, fontSize: '9px', height: '16px', minWidth: '14px', margin: '0 4px' }}>?</kbd> to toggle this reference
        </div>
      </div>

      {/* Fade-in animation */}
      <style>{`
        @keyframes shortcutFadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
