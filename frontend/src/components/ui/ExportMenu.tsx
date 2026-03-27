import { useState, useEffect, useRef, useCallback } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface ExportMenuProps {
  open: boolean;
  onClose: () => void;
  /** Anchor position (e.g. from the trigger button's bounding rect) */
  anchorRect?: DOMRect | null;
  onExportCSV?: () => void;
  onExportJSON?: () => void;
  onExportPNG?: () => void;
  onExportSVG?: () => void;
}

/* ── Export option definitions ────────────────────────────── */

interface ExportOption {
  id: string;
  label: string;
  icon: React.ReactNode;
  actionKey: keyof Pick<ExportMenuProps, 'onExportCSV' | 'onExportJSON' | 'onExportPNG' | 'onExportSVG'>;
}

const EXPORT_OPTIONS: ExportOption[] = [
  {
    id: 'csv',
    label: 'Export as CSV',
    actionKey: 'onExportCSV',
    icon: <ExportCSVIcon />,
  },
  {
    id: 'json',
    label: 'Export as JSON',
    actionKey: 'onExportJSON',
    icon: <ExportJSONIcon />,
  },
  {
    id: 'png',
    label: 'Export as PNG',
    actionKey: 'onExportPNG',
    icon: <ExportImageIcon />,
  },
  {
    id: 'svg',
    label: 'Export as SVG',
    actionKey: 'onExportSVG',
    icon: <ExportSVGIcon />,
  },
];

/* ── Component ────────────────────────────────────────────── */

export function ExportMenu({
  open,
  onClose,
  anchorRect,
  onExportCSV,
  onExportJSON,
  onExportPNG,
  onExportSVG,
}: ExportMenuProps) {
  const [activeIdx, setActiveIdx] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  const handlers: Record<string, (() => void) | undefined> = {
    onExportCSV,
    onExportJSON,
    onExportPNG,
    onExportSVG,
  };

  // Reset active index when opened
  useEffect(() => {
    if (open) setActiveIdx(0);
  }, [open]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!open) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((prev) => (prev + 1) % EXPORT_OPTIONS.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((prev) => (prev - 1 + EXPORT_OPTIONS.length) % EXPORT_OPTIONS.length);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const opt = EXPORT_OPTIONS[activeIdx];
        if (opt) {
          const handler = handlers[opt.actionKey];
          handler?.();
        }
        onClose();
        return;
      }
    },
    [open, activeIdx, onClose, handlers],
  );

  useEffect(() => {
    if (!open) return;
    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [open, handleKeyDown]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    window.addEventListener('mousedown', handleClick);
    return () => window.removeEventListener('mousedown', handleClick);
  }, [open, onClose]);

  if (!open) return null;

  // Position: prefer anchoring below-right of the anchor rect, or center of viewport
  const posStyle: React.CSSProperties = anchorRect
    ? {
        position: 'fixed',
        top: anchorRect.bottom + 4,
        left: anchorRect.left,
        zIndex: 250,
      }
    : {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 250,
      };

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Export options"
      style={{
        ...posStyle,
        minWidth: '200px',
        background: 'var(--color-surface-raised)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: '6px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.6)',
        padding: '4px 0',
        animation: 'exportMenuFadeIn 120ms ease-out both',
      }}
    >
      {EXPORT_OPTIONS.map((opt, idx) => {
        const isActive = idx === activeIdx;
        const handler = handlers[opt.actionKey];
        const isDisabled = !handler;

        return (
          <button
            key={opt.id}
            role="menuitem"
            type="button"
            disabled={isDisabled}
            className="flex w-full items-center gap-3 border-none px-3 text-left"
            style={{
              height: '34px',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: isDisabled
                ? 'var(--color-text-tertiary)'
                : isActive
                  ? 'var(--color-text-primary)'
                  : 'var(--color-text-secondary)',
              background: isActive ? 'var(--color-surface-overlay)' : 'transparent',
              cursor: isDisabled ? 'default' : 'pointer',
              opacity: isDisabled ? 0.5 : 1,
              transition: 'background 0.1s, color 0.1s',
            }}
            onMouseEnter={() => setActiveIdx(idx)}
            onClick={() => {
              if (!isDisabled) {
                handler?.();
                onClose();
              }
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-tertiary)' }}>
              {opt.icon}
            </span>
            <span>{opt.label}</span>
          </button>
        );
      })}

      {/* Footer hint */}
      <div
        style={{
          borderTop: '1px solid var(--color-surface-border)',
          margin: '4px 0 0',
          padding: '6px 12px 4px',
          fontFamily: 'var(--font-ui)',
          fontSize: '10px',
          color: 'var(--color-text-tertiary)',
          display: 'flex',
          gap: '8px',
        }}
      >
        <span>
          <kbd
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: '9px',
              padding: '0 3px',
              borderRadius: '2px',
              border: '1px solid var(--color-surface-border-strong)',
            }}
          >
            {'\u2191\u2193'}
          </kbd>{' '}
          navigate
        </span>
        <span>
          <kbd
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: '9px',
              padding: '0 3px',
              borderRadius: '2px',
              border: '1px solid var(--color-surface-border-strong)',
            }}
          >
            {'\u21B5'}
          </kbd>{' '}
          select
        </span>
        <span>
          <kbd
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: '9px',
              padding: '0 3px',
              borderRadius: '2px',
              border: '1px solid var(--color-surface-border-strong)',
            }}
          >
            Esc
          </kbd>{' '}
          close
        </span>
      </div>

      <style>{`
        @keyframes exportMenuFadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

/* ── Icons (14x14 stroke-based) ──────────────────────────── */

function ExportCSVIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <rect x="1.5" y="1.5" width="11" height="11" rx="1" />
      <line x1="1.5" y1="5" x2="12.5" y2="5" />
      <line x1="1.5" y1="8.5" x2="12.5" y2="8.5" />
      <line x1="5" y1="1.5" x2="5" y2="12.5" />
      <line x1="9" y1="1.5" x2="9" y2="12.5" />
    </svg>
  );
}

function ExportJSONIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M4.5 2C3.5 2 3 2.5 3 3.5v2c0 .5-.5 1-1 1 .5 0 1 .5 1 1v2c0 1 .5 1.5 1.5 1.5" />
      <path d="M9.5 2c1 0 1.5.5 1.5 1.5v2c0 .5.5 1 1 1-.5 0-1 .5-1 1v2c0 1-.5 1.5-1.5 1.5" />
    </svg>
  );
}

function ExportImageIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <rect x="1.5" y="2" width="11" height="10" rx="1" />
      <circle cx="4.5" cy="5" r="1" />
      <path d="M1.5 10l3-3 2 2 2.5-3L12.5 10" strokeLinejoin="round" />
    </svg>
  );
}

function ExportSVGIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <rect x="1.5" y="2" width="11" height="10" rx="1" />
      <path d="M4 9.5V7l1.5 1.5L7 7v2.5" />
      <circle cx="10" cy="5.5" r="1.5" />
    </svg>
  );
}
