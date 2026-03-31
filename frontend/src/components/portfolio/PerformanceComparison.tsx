import type { CSSProperties } from 'react';

export interface PerformancePeriod {
  label: string;
  portfolio: number;
  benchmark: number;
  alpha: number;
}

export interface PerformanceComparisonProps {
  periods: PerformancePeriod[];
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export function PerformanceComparison({ periods }: PerformanceComparisonProps) {
  const maxAbs = Math.max(...periods.flatMap((p) => [Math.abs(p.portfolio), Math.abs(p.benchmark)]), 0.001);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '60px 1fr 80px 80px 80px',
    gap: 'var(--space-2)',
    padding: '4px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={headerStyle}>
        <span>Period</span>
        <span />
        <span style={{ textAlign: 'right' }}>Portfolio</span>
        <span style={{ textAlign: 'right' }}>Benchmark</span>
        <span style={{ textAlign: 'right' }}>Alpha</span>
      </div>

      {periods.map((period, _i) => {
        const portPct = (Math.abs(period.portfolio) / maxAbs) * 100;
        const benchPct = (Math.abs(period.benchmark) / maxAbs) * 100;

        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '60px 1fr 80px 80px 80px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '5px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          transition: 'background 0.1s',
        };

        return (
          <div
            key={period.label}
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
                fontFamily: 'var(--font-data)',
                fontWeight: 600,
                color: 'var(--color-text-primary)',
                fontSize: 'var(--text-xs)',
              }}
            >
              {period.label}
            </span>

            {/* Mini bar visualization */}
            <div style={{ position: 'relative', height: '8px', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <div
                style={{
                  height: '6px',
                  width: `${portPct}%`,
                  background: signalColor(period.portfolio),
                  opacity: 0.7,
                  borderRadius: '2px',
                  maxWidth: '100%',
                  transition: 'width 0.3s',
                }}
              />
              <div
                style={{
                  height: '4px',
                  width: `${benchPct}%`,
                  background: 'var(--color-chart-3)',
                  opacity: 0.5,
                  borderRadius: '2px',
                  maxWidth: '100%',
                  position: 'absolute',
                  top: '50%',
                  transform: 'translateY(-50%)',
                }}
              />
            </div>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                color: signalColor(period.portfolio),
                textAlign: 'right',
                fontSize: 'var(--text-xs)',
              }}
            >
              {fmtPct(period.portfolio)}
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                color: signalColor(period.benchmark),
                textAlign: 'right',
                fontSize: 'var(--text-xs)',
              }}
            >
              {fmtPct(period.benchmark)}
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                color: signalColor(period.alpha),
                textAlign: 'right',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
              }}
            >
              {fmtPct(period.alpha)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default PerformanceComparison;
