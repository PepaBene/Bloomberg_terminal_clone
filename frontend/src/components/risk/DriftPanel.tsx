import type { CSSProperties } from 'react';

export interface DriftTarget {
  name: string;
  targetWeight: number;
  currentWeight: number;
  drift: number;
  maxDrift?: number;
}

export interface DriftPanelProps {
  targets: DriftTarget[];
}

export function DriftPanel({ targets }: DriftPanelProps) {
  const maxDriftAbs = Math.max(...targets.map((t) => Math.abs(t.drift)), 0.001);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '130px 70px 70px 1fr 60px',
    gap: 'var(--space-2)',
    padding: '4px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={headerStyle}>
        <span>Name</span>
        <span style={{ textAlign: 'right' }}>Target %</span>
        <span style={{ textAlign: 'right' }}>Current %</span>
        <span style={{ textAlign: 'center' }}>Drift</span>
        <span style={{ textAlign: 'right' }}>Drift %</span>
      </div>

      {targets.map((target, i) => {
        const exceeded =
          target.maxDrift !== undefined &&
          Math.abs(target.drift) > target.maxDrift;
        const barPct = (Math.abs(target.drift) / maxDriftAbs) * 40; // max 40% from center
        const isPositive = target.drift >= 0;
        const driftColor = exceeded
          ? 'var(--color-signal-warning)'
          : target.drift > 0
          ? 'var(--color-signal-positive)'
          : 'var(--color-signal-negative)';

        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '130px 70px 70px 1fr 60px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '6px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          background: exceeded ? 'rgba(255,163,0,0.06)' : 'transparent',
          transition: 'background 0.1s',
        };

        return (
          <div
            key={i}
            style={rowStyle}
            onMouseEnter={(e) => {
              if (!exceeded)
                (e.currentTarget as HTMLDivElement).style.background =
                  'var(--color-surface-raised)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = exceeded
                ? 'rgba(255,163,0,0.06)'
                : 'transparent';
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {target.name}
              {exceeded && (
                <span style={{ marginLeft: '6px', color: 'var(--color-signal-warning)', fontSize: '11px' }}>
                  &#9888;
                </span>
              )}
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                textAlign: 'right',
              }}
            >
              {target.targetWeight.toFixed(1)}%
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-primary)',
                textAlign: 'right',
              }}
            >
              {target.currentWeight.toFixed(1)}%
            </span>

            {/* Centered drift bar */}
            <div style={{ position: 'relative', height: '10px', display: 'flex', alignItems: 'center' }}>
              <div
                style={{
                  position: 'absolute',
                  left: '50%',
                  top: 0,
                  bottom: 0,
                  width: '1px',
                  background: 'var(--color-surface-border)',
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  height: '8px',
                  width: `${barPct}%`,
                  left: isPositive ? '50%' : `calc(50% - ${barPct}%)`,
                  background: driftColor,
                  borderRadius: '2px',
                }}
              />
            </div>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: driftColor,
                textAlign: 'right',
                fontWeight: exceeded ? 600 : 400,
              }}
            >
              {isPositive ? '+' : ''}{target.drift.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default DriftPanel;
