import type { CSSProperties } from 'react';

export interface VaRComponent {
  name: string;
  marginalVar: number;
  componentVar: number;
  percentContrib: number;
}

export interface VaRDecompositionProps {
  components: VaRComponent[];
}

export function VaRDecomposition({ components }: VaRDecompositionProps) {
  const sorted = [...components].sort((a, b) => b.percentContrib - a.percentContrib);
  const maxPct = Math.max(...sorted.map((c) => c.percentContrib), 0.001);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '140px 1fr 70px 70px 70px',
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
        <span>Contribution</span>
        <span style={{ textAlign: 'right' }}>% Contrib</span>
        <span style={{ textAlign: 'right' }}>Comp VaR</span>
        <span style={{ textAlign: 'right' }}>Marg VaR</span>
      </div>

      {sorted.map((comp, i) => {
        const barPct = (comp.percentContrib / maxPct) * 100;
        const isTotal = comp.name.toLowerCase() === 'total';

        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '140px 1fr 70px 70px 70px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '6px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          background: isTotal ? 'var(--color-surface-raised)' : 'transparent',
          transition: 'background 0.1s',
        };

        return (
          <div
            key={i}
            style={rowStyle}
            onMouseEnter={(e) => {
              if (!isTotal)
                (e.currentTarget as HTMLDivElement).style.background =
                  'var(--color-surface-raised)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = isTotal
                ? 'var(--color-surface-raised)'
                : 'transparent';
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-primary)',
                fontWeight: isTotal ? 700 : 400,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {comp.name}
            </span>

            <div style={{ height: '8px', display: 'flex', alignItems: 'center' }}>
              <div
                style={{
                  height: '8px',
                  width: `${barPct}%`,
                  background:
                    comp.percentContrib > 20
                      ? 'var(--color-signal-negative)'
                      : comp.percentContrib > 10
                      ? 'var(--color-signal-warning)'
                      : 'var(--color-signal-neutral)',
                  borderRadius: '2px',
                  maxWidth: '100%',
                }}
              />
            </div>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-primary)',
                textAlign: 'right',
              }}
            >
              {comp.percentContrib.toFixed(1)}%
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
              {comp.componentVar.toFixed(2)}%
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
              {comp.marginalVar.toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default VaRDecomposition;
