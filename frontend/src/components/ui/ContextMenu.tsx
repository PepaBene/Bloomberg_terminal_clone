import { useState } from 'react';
import type { CSSProperties } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface ContextMenuItem {
  label: string;
  icon?: string;
  onClick: () => void;
  separator?: boolean;
  disabled?: boolean;
}

export interface ContextMenuProps {
  items: ContextMenuItem[];
  x: number;
  y: number;
  onClose: () => void;
}

/* ── Keyframes injected once ─────────────────────────────── */

const menuKeyframes = `
@keyframes menuIn {
  from { opacity: 0; transform: scale(0.96) translateY(-4px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);    }
}
`;

/* ── ContextMenu component ───────────────────────────────── */

export function ContextMenu({ items, x, y, onClose }: ContextMenuProps) {
  /* ── Clamp to viewport edges ────────────────────────────── */
  const menuWidth = 200;
  const estimatedMenuHeight = items.length * 28 + 8; // rough: 28px per item + 8px padding
  const clampedX = Math.min(x, window.innerWidth  - menuWidth  - 8);
  const clampedY = Math.min(y, window.innerHeight - estimatedMenuHeight - 8);

  const backdropStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 8999,
  };

  const panelStyle: CSSProperties = {
    position: 'fixed',
    left: clampedX,
    top: clampedY,
    zIndex: 9000,
    background: 'var(--color-surface-overlay)',
    border: '1px solid var(--color-surface-border-strong)',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow-float)',
    minWidth: menuWidth,
    padding: 'var(--space-1) 0',
    animation: 'menuIn 120ms ease-out',
  };

  return (
    <>
      <style>{menuKeyframes}</style>

      {/* Invisible backdrop — clicking closes the menu */}
      <div style={backdropStyle} onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />

      {/* Menu panel */}
      <div className="animate-in" style={panelStyle}>
        {items.map((item, idx) => {
          /* Separator */
          if (item.separator) {
            return (
              <div
                key={idx}
                style={{
                  height: '1px',
                  background: 'var(--color-surface-border)',
                  margin: 'var(--space-1) 0',
                }}
              />
            );
          }

          const isFirst = idx === 0 || (idx === 0 && !items[0]?.separator);

          const itemStyle: CSSProperties = {
            height: '28px',
            padding: '0 var(--space-3)',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 'var(--space-2)',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: isFirst
              ? 'var(--color-accent-primary)'
              : 'var(--color-text-secondary)',
            cursor: item.disabled ? 'not-allowed' : 'pointer',
            pointerEvents: item.disabled ? 'none' : undefined,
            opacity: item.disabled ? 0.4 : 1,
            userSelect: 'none',
            whiteSpace: 'nowrap',
          };

          return (
            <div
              key={idx}
              style={itemStyle}
              onClick={() => {
                if (!item.disabled) {
                  item.onClick();
                  onClose();
                }
              }}
              onMouseEnter={(e) => {
                if (!item.disabled) {
                  (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
                  (e.currentTarget as HTMLDivElement).style.color = 'var(--color-text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.background = '';
                (e.currentTarget as HTMLDivElement).style.color = isFirst
                  ? 'var(--color-accent-primary)'
                  : 'var(--color-text-secondary)';
              }}
            >
              {item.icon && <span style={{ fontSize: '12px', lineHeight: 1 }}>{item.icon}</span>}
              {item.label}
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ── useContextMenu hook ─────────────────────────────────── */

export function useContextMenu() {
  const [menu, setMenu] = useState<{ x: number; y: number; items: ContextMenuItem[] } | null>(null);

  const open = (e: React.MouseEvent, items: ContextMenuItem[]) => {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, items });
  };

  const close = () => setMenu(null);

  return { menu, open, close };
}
