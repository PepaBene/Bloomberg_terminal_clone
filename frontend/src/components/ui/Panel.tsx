import { type ReactNode, useState } from 'react';
import clsx from 'clsx';

export interface PanelProps {
  /** Panel title shown in the header */
  title: string;
  /** Optional subtitle shown next to the title */
  subtitle?: string;
  /** Optional icon element rendered before the title */
  icon?: ReactNode;
  /** Content to render in the header actions area (right side) */
  headerActions?: ReactNode;
  /** Panel body content */
  children: ReactNode;
  /** Additional CSS class names */
  className?: string;
  /** Whether the panel starts in expanded/fullscreen mode */
  defaultExpanded?: boolean;
  /** Callback when expand button is clicked */
  onExpand?: () => void;
  /** Callback when popout button is clicked */
  onPopout?: () => void;
  /** Callback when menu button is clicked */
  onMenu?: () => void;
}

export function Panel({
  title,
  subtitle,
  icon,
  headerActions,
  children,
  className,
  defaultExpanded = false,
  onExpand,
  onPopout,
  onMenu,
}: PanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const handleExpand = () => {
    setExpanded((prev) => !prev);
    onExpand?.();
  };

  return (
    <div
      className={clsx(
        'flex flex-col overflow-hidden rounded-[var(--border-radius-md,4px)]',
        expanded && 'fixed inset-0 z-50',
        className,
      )}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
      }}
    >
      {/* Panel Header - 32px height */}
      <div
        className="flex shrink-0 items-center gap-2 px-[var(--panel-padding)] select-none"
        style={{
          height: '32px',
          borderBottom: '1px solid var(--color-surface-border)',
        }}
      >
        {/* Left: icon + title + subtitle */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {icon && (
            <span
              className="flex shrink-0 items-center"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {icon}
            </span>
          )}
          <span
            className="truncate font-medium"
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-md)',
              color: 'var(--color-text-primary)',
              lineHeight: '1.2',
            }}
          >
            {title}
          </span>
          {subtitle && (
            <span
              className="truncate"
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-secondary)',
                lineHeight: '1.2',
              }}
            >
              {subtitle}
            </span>
          )}
        </div>

        {/* Center/Right: filter chips or custom header actions */}
        {headerActions && (
          <div className="flex shrink-0 items-center gap-1">
            {headerActions}
          </div>
        )}

        {/* Right: expand / popout / menu buttons */}
        <div className="flex shrink-0 items-center gap-0.5">
          <PanelHeaderButton
            onClick={handleExpand}
            label={expanded ? 'Collapse' : 'Expand'}
          >
            {'\u229E'}
          </PanelHeaderButton>
          {onPopout && (
            <PanelHeaderButton onClick={onPopout} label="Pop out">
              {'\u2197'}
            </PanelHeaderButton>
          )}
          {onMenu && (
            <PanelHeaderButton onClick={onMenu} label="Menu">
              {'\u22EE'}
            </PanelHeaderButton>
          )}
        </div>
      </div>

      {/* Panel Content - scrolls independently */}
      <div
        className="flex-1 overflow-auto"
        style={{ padding: 'var(--panel-padding)' }}
      >
        {children}
      </div>
    </div>
  );
}

/* ── Internal header button ───────────────────────────────── */

function PanelHeaderButton({
  children,
  onClick,
  label,
}: {
  children: ReactNode;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex cursor-pointer items-center justify-center rounded-[2px]"
      style={{
        width: '22px',
        height: '22px',
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text-tertiary)',
        background: 'transparent',
        border: 'none',
        transition: 'color 0.15s, background 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = 'var(--color-text-primary)';
        e.currentTarget.style.background = 'var(--color-surface-overlay)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = 'var(--color-text-tertiary)';
        e.currentTarget.style.background = 'transparent';
      }}
    >
      {children}
    </button>
  );
}
