import clsx from 'clsx';

export interface ChangeIndicatorProps {
  /** Numeric change value (e.g. 12.3, -4.5, 0) */
  value: number;
  /** Format as percentage (appends %) — default true */
  percent?: boolean;
  /** Number of decimal places (default: 1) */
  decimals?: number;
  /** Additional CSS class */
  className?: string;
}

export function ChangeIndicator({
  value,
  percent = true,
  decimals = 1,
  className,
}: ChangeIndicatorProps) {
  const direction = value > 0 ? 'positive' : value < 0 ? 'negative' : 'flat';

  const color =
    direction === 'positive'
      ? 'var(--color-signal-positive)'
      : direction === 'negative'
        ? 'var(--color-signal-negative)'
        : 'var(--color-signal-neutral)';

  const arrow =
    direction === 'positive'
      ? '\u25B2'
      : direction === 'negative'
        ? '\u25BC'
        : '';

  const sign = value > 0 ? '+' : '';
  const formatted = `${sign}${value.toFixed(decimals)}${percent ? '%' : ''}`;

  return (
    <span
      className={clsx('inline-flex items-center gap-0.5', className)}
      style={{
        fontFamily: 'var(--font-data)',
        fontSize: 'inherit',
        fontVariantNumeric: 'tabular-nums',
        color,
        lineHeight: '1.2',
        whiteSpace: 'nowrap',
      }}
    >
      {arrow && (
        <span style={{ fontSize: '0.65em', lineHeight: '1' }}>{arrow}</span>
      )}
      {formatted}
    </span>
  );
}
