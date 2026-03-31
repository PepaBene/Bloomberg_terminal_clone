import type { CSSProperties } from 'react';

export interface ThesisData {
  id: string;
  ticker: string;
  direction: 'LONG' | 'SHORT';
  title: string;
  summary: string;
  keyDrivers: string[];
  risks: string[];
  targetPrice?: number;
  conviction: 'HIGH' | 'MEDIUM' | 'LOW';
  createdAt: string;
}

export interface ThesisCardProps {
  thesis: ThesisData;
  onOpen?: (id: string) => void;
}

const CONVICTION_COLOR: Record<string, string> = {
  HIGH: 'var(--color-quality-5)',
  MEDIUM: 'var(--color-quality-3)',
  LOW: 'var(--color-quality-2)',
};

function fmtDate(str: string): string {
  return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function ThesisCard({ thesis, onOpen }: ThesisCardProps) {
  const isLong = thesis.direction === 'LONG';
  const directionColor = isLong ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
  const convColor = CONVICTION_COLOR[thesis.conviction] ?? 'var(--color-text-secondary)';

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: `1px solid var(--color-surface-border)`,
    borderTop: `3px solid ${directionColor}`,
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  return (
    <div className="animate-in" style={cardStyle}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              color: 'var(--color-accent-primary)',
              background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-sm)',
            }}>
              {thesis.ticker}
            </span>
            <span style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              color: directionColor,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              {isLong ? '↑' : '↓'} {thesis.direction}
            </span>
            <span style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
            }}>
              {fmtDate(thesis.createdAt)}
            </span>
          </div>
          <h3 style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            margin: 0,
          }}>
            {thesis.title}
          </h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: convColor,
            background: `color-mix(in srgb, ${convColor} 12%, transparent)`,
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {thesis.conviction}
          </span>
          {thesis.targetPrice != null && (
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
              PT: ${thesis.targetPrice.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Summary */}
      <p style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text-secondary)',
        margin: 0,
        lineHeight: 1.5,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'],
      }}>
        {thesis.summary}
      </p>

      {/* Drivers + Risks */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)', fontWeight: 600, marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Key Drivers
          </div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {thesis.keyDrivers.slice(0, 3).map((d, i) => (
              <li key={i} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', display: 'flex', gap: '4px' }}>
                <span style={{ color: 'var(--color-signal-positive)', flexShrink: 0 }}>+</span>
                {d}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)', fontWeight: 600, marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Risks
          </div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {thesis.risks.slice(0, 3).map((r, i) => (
              <li key={i} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', display: 'flex', gap: '4px' }}>
                <span style={{ color: 'var(--color-signal-negative)', flexShrink: 0 }}>–</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {onOpen && (
        <div style={{ borderTop: '1px solid var(--color-surface-border)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
          <button
            type="button"
            onClick={() => onOpen(thesis.id)}
            style={{
              background: 'none',
              border: `1px solid ${directionColor}`,
              borderRadius: 'var(--radius-sm)',
              padding: '3px 10px',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: directionColor,
              cursor: 'pointer',
            }}
          >
            View Full Thesis →
          </button>
        </div>
      )}
    </div>
  );
}

export default ThesisCard;
