import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface PeriodSelectorProps {
  mode: 'annual' | 'quarterly';
  onModeChange: (mode: 'annual' | 'quarterly') => void;
  periodCount: number;
  onPeriodCountChange: (count: number) => void;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const PERIOD_OPTIONS = [4, 8, 12, 20] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function PeriodSelector({
  mode,
  onModeChange,
  periodCount,
  onPeriodCountChange,
  className,
}: PeriodSelectorProps) {
  return (
    <div className={clsx('flex items-center gap-3', className)}>
      {/* Annual / Quarterly toggle */}
      <div
        className="flex"
        style={{
          border: '1px solid var(--color-surface-border)',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
        }}
      >
        {(['annual', 'quarterly'] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onModeChange(m)}
            style={{
              padding: '4px 12px',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              cursor: 'pointer',
              border: 'none',
              transition: 'all var(--transition-fast)',
              background:
                mode === m
                  ? 'var(--color-accent-primary)'
                  : 'var(--color-surface-base)',
              color:
                mode === m
                  ? 'var(--color-text-primary)'
                  : 'var(--color-text-secondary)',
            }}
          >
            {m === 'annual' ? 'Annual' : 'Quarterly'}
          </button>
        ))}
      </div>

      {/* Period count selector */}
      <div className="flex items-center gap-1">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            marginRight: 4,
          }}
        >
          Periods:
        </span>
        {PERIOD_OPTIONS.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onPeriodCountChange(n)}
            style={{
              padding: '3px 8px',
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontVariantNumeric: 'tabular-nums',
              cursor: 'pointer',
              border: '1px solid',
              borderColor:
                periodCount === n
                  ? 'var(--color-accent-primary)'
                  : 'var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              background:
                periodCount === n
                  ? 'rgba(59, 130, 246, 0.15)'
                  : 'var(--color-surface-base)',
              color:
                periodCount === n
                  ? 'var(--color-accent-primary)'
                  : 'var(--color-text-secondary)',
              transition: 'all var(--transition-fast)',
            }}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}
