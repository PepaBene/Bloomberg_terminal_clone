import { useEffect, type ReactNode, type CSSProperties } from 'react';

export interface DrillDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: number | string;
}

export function DrillDrawer({
  open,
  onClose,
  title,
  children,
  width = 480,
}: DrillDrawerProps) {
  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const backdropStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.6)',
    zIndex: 9000,
    opacity: open ? 1 : 0,
    pointerEvents: open ? 'auto' : 'none',
    transition: 'opacity var(--transition-normal)',
  };

  const drawerStyle: CSSProperties = {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    width: typeof width === 'number' ? `${width}px` : width,
    background: 'var(--color-surface-base)',
    borderLeft: '1px solid var(--color-surface-border-strong)',
    zIndex: 9001,
    display: 'flex',
    flexDirection: 'column',
    transform: open ? 'translateX(0)' : `translateX(100%)`,
    transition: 'transform 300ms ease-out',
    boxShadow: 'var(--shadow-float)',
  };

  const drawerHeaderStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--space-3) var(--panel-padding)',
    borderBottom: '1px solid var(--color-surface-border)',
    flexShrink: 0,
  };

  const drawerBodyStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: 'var(--panel-padding)',
  };

  return (
    <>
      <div style={backdropStyle} onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={drawerStyle}
      >
        <div style={drawerHeaderStyle}>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-base)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
          }}>
            {title}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-text-tertiary)',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-lg)',
              lineHeight: 1,
              padding: '2px 6px',
              borderRadius: 'var(--radius-sm)',
              transition: 'color var(--transition-fast), background var(--transition-fast)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = 'var(--color-text-primary)';
              e.currentTarget.style.background = 'var(--color-surface-raised)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'var(--color-text-tertiary)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            ✕
          </button>
        </div>
        <div style={drawerBodyStyle}>{children}</div>
      </div>
    </>
  );
}

export default DrillDrawer;
