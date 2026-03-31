import type { CSSProperties } from 'react';

export interface ScenarioImpact {
  name: string;
  probability: number;
  marketImpact: number;
  portfolioImpact: number;
  keyRisks: string[];
}

export interface ScenarioImpactTableProps {
  scenarios: ScenarioImpact[];
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

export function ScenarioImpactTable({ scenarios }: ScenarioImpactTableProps) {
  const maxProb = Math.max(...scenarios.map(s => s.probability), 1);

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 80px 80px 80px 1fr',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-surface-raised)',
    borderBottom: '1px solid var(--color-surface-border-strong)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={headerStyle}>
        <span>Scenario</span>
        <span style={{ textAlign: 'right' }}>Prob.</span>
        <span style={{ textAlign: 'right' }}>Market</span>
        <span style={{ textAlign: 'right' }}>Portfolio</span>
        <span>Key Risks</span>
      </div>
      {scenarios.map((s, i) => {
        const probBarPct = (s.probability / maxProb) * 100;
        return (
          <div
            key={i}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 80px 80px 80px 1fr',
              gap: 'var(--space-2)',
              alignItems: 'center',
              padding: 'var(--space-2) var(--space-3)',
              borderBottom: i < scenarios.length - 1 ? '1px solid var(--color-surface-border)' : 'none',
              transition: 'background var(--transition-fast)',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-raised)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            {/* Name */}
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>
              {s.name}
            </span>

            {/* Probability with background bar */}
            <div style={{ position: 'relative', textAlign: 'right' }}>
              <div style={{
                position: 'absolute',
                inset: 0,
                right: 'auto',
                width: `${probBarPct}%`,
                background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
                borderRadius: 'var(--radius-sm)',
              }} />
              <span style={{
                position: 'relative',
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                fontVariantNumeric: 'tabular-nums',
                color: 'var(--color-text-secondary)',
              }}>
                {s.probability.toFixed(0)}%
              </span>
            </div>

            {/* Market impact */}
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontVariantNumeric: 'tabular-nums',
              color: signalColor(s.marketImpact),
              textAlign: 'right',
            }}>
              {fmtPct(s.marketImpact)}
            </span>

            {/* Portfolio impact */}
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontVariantNumeric: 'tabular-nums',
              color: signalColor(s.portfolioImpact),
              textAlign: 'right',
              fontWeight: 600,
            }}>
              {fmtPct(s.portfolioImpact)}
            </span>

            {/* Key risks */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
              {s.keyRisks.slice(0, 3).map((r, j) => (
                <span key={j} style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  background: 'var(--color-surface-overlay)',
                  border: '1px solid var(--color-surface-border)',
                  padding: '0 4px',
                  borderRadius: 'var(--radius-sm)',
                }}>
                  {r}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default ScenarioImpactTable;
