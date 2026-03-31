import { type ReactNode } from 'react';
import clsx from 'clsx';
import { ContextMenu, useContextMenu } from './ContextMenu';

export interface KPICardProps {
  /** Short metric label (e.g. "Market Cap") */
  label: string;
  /** The hero metric value (e.g. "$4.2B") */
  value: string | number;
  /** Change amount or percentage string (e.g. "+12.3%") */
  change?: string;
  /** Direction of change for coloring */
  changeDirection?: 'positive' | 'negative' | 'neutral';
  /** Optional subtitle or secondary text */
  subtitle?: string;
  /** Optional sparkline or other inline content */
  sparkline?: ReactNode;
  /** Additional CSS class */
  className?: string;
  /** Called when "Drill into this value" is selected from the right-click menu */
  onDrillDown?: () => void;
}

export function KPICard({
  label,
  value,
  change,
  changeDirection = 'neutral',
  subtitle,
  sparkline,
  className,
  onDrillDown,
}: KPICardProps) {
  const { menu: ctxMenu, open: openCtxMenu, close: closeCtxMenu } = useContextMenu();

  const changeColor =
    changeDirection === 'positive'
      ? 'var(--color-signal-positive)'
      : changeDirection === 'negative'
        ? 'var(--color-signal-negative)'
        : 'var(--color-signal-neutral)';

  const changeArrow =
    changeDirection === 'positive'
      ? '\u25B2'
      : changeDirection === 'negative'
        ? '\u25BC'
        : '';

  return (
    <>
    <div
      className={clsx(
        'flex flex-col gap-1 rounded-[var(--border-radius-md,4px)] p-[var(--panel-padding)]',
        className,
      )}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
      }}
      onContextMenu={(e) => {
        openCtxMenu(e, [
          {
            label: 'Drill into this value',
            onClick: () => onDrillDown?.(),
          },
          {
            label: 'Copy value',
            onClick: () => navigator.clipboard.writeText(String(value ?? '')),
          },
        ]);
      }}
    >
      {/* Label */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-secondary)',
          lineHeight: '1.2',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </span>

      {/* Hero number + change */}
      <div className="flex items-baseline gap-2">
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            lineHeight: '1.2',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {value}
        </span>

        {change && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              color: changeColor,
              fontVariantNumeric: 'tabular-nums',
              lineHeight: '1.2',
            }}
          >
            {changeArrow && (
              <span style={{ fontSize: '8px', marginRight: '2px' }}>
                {changeArrow}
              </span>
            )}
            {change}
          </span>
        )}
      </div>

      {/* Subtitle */}
      {subtitle && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            lineHeight: '1.3',
          }}
        >
          {subtitle}
        </span>
      )}

      {/* Sparkline placeholder */}
      {sparkline && <div className="mt-1">{sparkline}</div>}
    </div>
    {ctxMenu && (
      <ContextMenu
        items={ctxMenu.items}
        x={ctxMenu.x}
        y={ctxMenu.y}
        onClose={closeCtxMenu}
      />
    )}
    </>
  );
}
