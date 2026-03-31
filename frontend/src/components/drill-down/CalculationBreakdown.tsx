import type { CSSProperties } from 'react';

export interface BreakdownStep {
  label: string;
  formula?: string;
  value: number | string;
  note?: string;
}

export interface CalculationBreakdownProps {
  title: string;
  steps: BreakdownStep[];
  result: { label: string; value: string | number };
}

export function CalculationBreakdown({ title, steps, result }: CalculationBreakdownProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  };

  const headerStyle: CSSProperties = {
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-surface-raised)',
    borderBottom: '1px solid var(--color-surface-border)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  };

  const stepRowStyle = (last: boolean): CSSProperties => ({
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 'var(--space-3)',
    padding: 'var(--space-2) var(--space-3)',
    borderBottom: last ? 'none' : '1px solid var(--color-surface-border)',
    transition: 'background var(--transition-fast)',
  });

  const resultRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 'var(--space-3)',
    padding: 'var(--space-3)',
    background: 'var(--color-surface-overlay)',
    borderTop: '2px solid var(--color-surface-border-strong)',
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={headerStyle}>{title}</div>
      {steps.map((step, i) => (
        <div
          key={i}
          style={stepRowStyle(i === steps.length - 1)}
          onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-raised)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
        >
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
              {step.label}
            </span>
            {step.formula && (
              <span style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-tertiary)',
                background: 'var(--color-surface-overlay)',
                padding: '1px 6px',
                borderRadius: 'var(--radius-sm)',
                display: 'inline-block',
              }}>
                {step.formula}
              </span>
            )}
            {step.note && (
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
                {step.note}
              </span>
            )}
          </div>
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-sm)',
            fontVariantNumeric: 'tabular-nums',
            color: 'var(--color-text-primary)',
            textAlign: 'right',
            flexShrink: 0,
          }}>
            {typeof step.value === 'number' ? step.value.toLocaleString() : step.value}
          </span>
        </div>
      ))}
      <div style={resultRowStyle}>
        <span style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}>
          {result.label}
        </span>
        <span style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xl)',
          fontWeight: 700,
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--color-accent-primary)',
        }}>
          {typeof result.value === 'number' ? result.value.toLocaleString() : result.value}
        </span>
      </div>
    </div>
  );
}

export default CalculationBreakdown;
