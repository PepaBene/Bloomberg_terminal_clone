import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import { BarChartComponent } from '../charts/BarChart';
import { CHART_THEME } from '../charts/chartTheme';

export interface PerformancePeriod {
  label: string;
  portfolio: number;
  benchmark: number;
  alpha: number;
}

export interface PerformanceComparisonProps {
  periods: PerformancePeriod[];
  height?: number;
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

const rowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 8px',
  borderBottom: '1px solid var(--color-surface-border)',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
};

export function PerformanceComparison({ periods, height = 220 }: PerformanceComparisonProps) {
  const data = useMemo(
    () => periods.map((p) => ({ label: p.label, portfolio: p.portfolio, benchmark: p.benchmark })),
    [periods],
  );

  return (
    <div className="animate-in">
      <BarChartComponent
        data={data}
        xKey="label"
        height={height}
        showLegend
        showMeanLine={false}
        yAxisFormat={(v) => `${v.toFixed(1)}%`}
        bars={[
          { key: 'portfolio', name: 'Portfolio', color: CHART_THEME.colors.accent },
          { key: 'benchmark', name: 'Benchmark', color: CHART_THEME.colors.series[2] as string },
        ]}
      />

      {/* Alpha — the derived portfolio-minus-benchmark figure, called out separately from the two-series chart above */}
      <div style={{ marginTop: 'var(--space-2)' }}>
        {periods.map((p) => (
          <div key={p.label} style={rowStyle}>
            <span style={{ color: 'var(--color-text-secondary)' }}>{p.label} alpha</span>
            <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: signalColor(p.alpha) }}>
              {fmtPct(p.alpha)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default PerformanceComparison;
