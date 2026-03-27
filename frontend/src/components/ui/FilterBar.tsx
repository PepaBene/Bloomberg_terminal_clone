import clsx from 'clsx';

export interface FilterChip {
  /** Display label */
  label: string;
  /** Unique filter value / identifier */
  value: string;
  /** Whether this chip is currently active */
  active: boolean;
}

export interface FilterBarProps {
  /** Filter chip definitions */
  filters: FilterChip[];
  /** Called when a chip is toggled — receives the filter value */
  onToggle: (value: string) => void;
  /** Additional CSS class */
  className?: string;
}

export function FilterBar({ filters, onToggle, className }: FilterBarProps) {
  return (
    <div
      className={clsx('flex flex-wrap items-center gap-1', className)}
      role="group"
      aria-label="Filters"
    >
      {filters.map((chip) => (
        <button
          key={chip.value}
          type="button"
          role="switch"
          aria-checked={chip.active}
          onClick={() => onToggle(chip.value)}
          className="cursor-pointer rounded-full border-none"
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            lineHeight: '1',
            padding: '4px 10px',
            color: chip.active
              ? 'var(--color-text-inverse)'
              : 'var(--color-text-secondary)',
            background: chip.active
              ? 'var(--color-accent-primary)'
              : 'var(--color-surface-overlay)',
            transition: 'background 0.15s, color 0.15s',
            whiteSpace: 'nowrap',
          }}
          onMouseEnter={(e) => {
            if (!chip.active) {
              e.currentTarget.style.color = 'var(--color-text-primary)';
              e.currentTarget.style.background =
                'var(--color-surface-border)';
            }
          }}
          onMouseLeave={(e) => {
            if (!chip.active) {
              e.currentTarget.style.color = 'var(--color-text-secondary)';
              e.currentTarget.style.background =
                'var(--color-surface-overlay)';
            }
          }}
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
