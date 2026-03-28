import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CommonSizeToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label?: string;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CommonSizeToggle({
  enabled,
  onChange,
  label = '% of Revenue',
  className,
}: CommonSizeToggleProps) {
  return (
    <label
      className={clsx('inline-flex items-center gap-2 cursor-pointer select-none', className)}
    >
      {/* Toggle track */}
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => onChange(!enabled)}
        style={{
          position: 'relative',
          width: 28,
          height: 16,
          borderRadius: 8,
          border: '1px solid',
          borderColor: enabled
            ? 'var(--color-accent-primary)'
            : 'var(--color-surface-border-strong)',
          background: enabled
            ? 'var(--color-accent-primary)'
            : 'var(--color-surface-overlay)',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
          padding: 0,
          flexShrink: 0,
        }}
      >
        {/* Toggle knob */}
        <span
          style={{
            display: 'block',
            position: 'absolute',
            top: 2,
            left: enabled ? 13 : 2,
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: enabled
              ? 'var(--color-text-primary)'
              : 'var(--color-text-tertiary)',
            transition: 'left var(--transition-fast)',
          }}
        />
      </button>

      {/* Label */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: enabled
            ? 'var(--color-accent-primary)'
            : 'var(--color-text-secondary)',
          transition: 'color var(--transition-fast)',
        }}
      >
        {label}
      </span>
    </label>
  );
}
