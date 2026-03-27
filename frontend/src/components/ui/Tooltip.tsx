import {
  useState,
  useRef,
  useEffect,
  useCallback,
  type ReactNode,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { createPortal } from 'react-dom';
import clsx from 'clsx';

/* ── Types ────────────────────────────────────────────────── */

export interface TooltipRow {
  label: string;
  value: ReactNode;
}

export interface TooltipProps {
  /** Key-value rows to display */
  rows: TooltipRow[];
  /** The element that triggers the tooltip */
  children: ReactNode;
  /** Whether the tooltip is pinned (stays visible until dismissed) */
  pinned?: boolean;
  /** Called when the tooltip is pinned via right-click */
  onPin?: (pinned: boolean) => void;
  /** Additional CSS class for the tooltip popup */
  className?: string;
}

/* ── Component ────────────────────────────────────────────── */

export function Tooltip({
  rows,
  children,
  pinned: controlledPinned,
  onPin,
  className,
}: TooltipProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [internalPinned, setInternalPinned] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  const isPinned = controlledPinned ?? internalPinned;

  const updatePosition = useCallback((e: ReactMouseEvent) => {
    setPos({ x: e.clientX + 12, y: e.clientY + 12 });
  }, []);

  const handleMouseEnter = useCallback(
    (e: ReactMouseEvent) => {
      if (!isPinned) {
        setVisible(true);
        updatePosition(e);
      }
    },
    [isPinned, updatePosition],
  );

  const handleMouseMove = useCallback(
    (e: ReactMouseEvent) => {
      if (!isPinned) updatePosition(e);
    },
    [isPinned, updatePosition],
  );

  const handleMouseLeave = useCallback(() => {
    if (!isPinned) setVisible(false);
  }, [isPinned]);

  const handleContextMenu = useCallback(
    (e: ReactMouseEvent) => {
      e.preventDefault();
      const next = !isPinned;
      setInternalPinned(next);
      onPin?.(next);
      if (next) {
        setVisible(true);
        setPos({ x: e.clientX + 12, y: e.clientY + 12 });
      }
    },
    [isPinned, onPin],
  );

  // Close pinned tooltip on Escape
  useEffect(() => {
    if (!isPinned) return;
    const handler = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setInternalPinned(false);
        onPin?.(false);
        setVisible(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isPinned, onPin]);

  const showTooltip = visible || isPinned;

  return (
    <>
      <div
        ref={wrapperRef}
        className="inline-block"
        onMouseEnter={handleMouseEnter}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onContextMenu={handleContextMenu}
      >
        {children}
      </div>

      {showTooltip &&
        rows.length > 0 &&
        createPortal(
          <TooltipPopup
            rows={rows}
            x={pos.x}
            y={pos.y}
            pinned={isPinned}
            className={className}
          />,
          document.body,
        )}
    </>
  );
}

/* ── Popup ─────────────────────────────────────────────────── */

function TooltipPopup({
  rows,
  x,
  y,
  pinned,
  className,
}: {
  rows: TooltipRow[];
  x: number;
  y: number;
  pinned: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [adjusted, setAdjusted] = useState({ x, y });

  // Adjust position if tooltip overflows viewport
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    let nx = x;
    let ny = y;
    if (x + rect.width > window.innerWidth - 8) {
      nx = x - rect.width - 24;
    }
    if (y + rect.height > window.innerHeight - 8) {
      ny = y - rect.height - 24;
    }
    setAdjusted({ x: Math.max(4, nx), y: Math.max(4, ny) });
  }, [x, y]);

  return (
    <div
      ref={ref}
      className={clsx('fixed z-[200] pointer-events-none', pinned && 'pointer-events-auto', className)}
      style={{
        left: adjusted.x,
        top: adjusted.y,
        background: 'var(--color-surface-raised)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
        padding: '6px 10px',
        minWidth: '120px',
        maxWidth: '320px',
      }}
    >
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-secondary)',
                  paddingRight: '12px',
                  paddingTop: i > 0 ? '2px' : 0,
                  whiteSpace: 'nowrap',
                  verticalAlign: 'top',
                }}
              >
                {row.label}
              </td>
              <td
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                  paddingTop: i > 0 ? '2px' : 0,
                  textAlign: 'right',
                  whiteSpace: 'nowrap',
                  verticalAlign: 'top',
                }}
              >
                {row.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {pinned && (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: '9px',
            color: 'var(--color-text-tertiary)',
            marginTop: '4px',
            textAlign: 'center',
          }}
        >
          Right-click to unpin {'|'} Esc to close
        </div>
      )}
    </div>
  );
}
