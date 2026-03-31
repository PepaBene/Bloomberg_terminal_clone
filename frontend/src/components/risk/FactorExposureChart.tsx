import type { CSSProperties } from 'react';

export interface FactorBeta {
  name: string;
  beta: number;
  tStat: number;
  significant: boolean;
}

export interface FactorExposureChartProps {
  factors: FactorBeta[];
}

export function FactorExposureChart({ factors }: FactorExposureChartProps) {
  const maxAbs = Math.max(...factors.map((f) => Math.abs(f.beta)), 0.001);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '130px 1fr 60px 70px',
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
        <span>Factor</span>
        <span>Beta</span>
        <span style={{ textAlign: 'right' }}>Beta</span>
        <span style={{ textAlign: 'right' }}>t-Stat</span>
      </div>

      {factors.map((factor, i) => {
        const barPct = (Math.abs(factor.beta) / maxAbs) * 48; // max 48% from center
        const isPositive = factor.beta >= 0;
        const barColor = !factor.significant
          ? 'var(--color-text-tertiary)'
          : isPositive
          ? 'var(--color-signal-positive)'
          : 'var(--color-signal-negative)';

        const tStatColor = Math.abs(factor.tStat) >= 2
          ? 'var(--color-text-primary)'
          : 'var(--color-text-tertiary)';

        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '130px 1fr 60px 70px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '6px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          transition: 'background 0.1s',
          opacity: factor.significant ? 1 : 0.55,
        };

        return (
          <div
            key={i}
            style={rowStyle}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'transparent';
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
              {factor.name}
            </span>

            {/* Centered bar track */}
            <div
              style={{
                position: 'relative',
                height: '10px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {/* Zero line */}
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
              {/* Bar */}
              <div
                style={{
                  position: 'absolute',
                  height: '8px',
                  width: `${barPct}%`,
                  left: isPositive ? '50%' : `calc(50% - ${barPct}%)`,
                  background: barColor,
                  borderRadius: '2px',
                }}
              />
            </div>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: barColor,
                textAlign: 'right',
              }}
            >
              {factor.beta >= 0 ? '+' : ''}{factor.beta.toFixed(2)}
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: tStatColor,
                textAlign: 'right',
              }}
            >
              {factor.tStat.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default FactorExposureChart;
