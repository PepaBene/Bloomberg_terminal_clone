import clsx from 'clsx';

export type SignalVariant =
  | 'positive'
  | 'negative'
  | 'warning'
  | 'neutral'
  | 'highlight';

export interface SignalBadgeProps {
  /** Badge text label */
  label: string;
  /** Color variant */
  variant?: SignalVariant;
  /** Show a small dot indicator before the label */
  dot?: boolean;
  /** Additional CSS class */
  className?: string;
}

const VARIANT_COLORS: Record<SignalVariant, string> = {
  positive: 'var(--color-signal-positive)',
  negative: 'var(--color-signal-negative)',
  warning: 'var(--color-signal-warning)',
  neutral: 'var(--color-signal-neutral)',
  highlight: 'var(--color-signal-highlight)',
};

export function SignalBadge({
  label,
  variant = 'neutral',
  dot = false,
  className,
}: SignalBadgeProps) {
  const color = VARIANT_COLORS[variant];

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full',
        className,
      )}
      style={{
        fontFamily: 'var(--font-data)',
        fontSize: 'var(--text-xs)',
        fontWeight: 500,
        color,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        lineHeight: '1',
        padding: '2px 8px',
        border: `1px solid ${color}`,
        background: 'transparent',
        whiteSpace: 'nowrap',
      }}
    >
      {dot && (
        <span
          style={{
            width: '5px',
            height: '5px',
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
      )}
      {label}
    </span>
  );
}
