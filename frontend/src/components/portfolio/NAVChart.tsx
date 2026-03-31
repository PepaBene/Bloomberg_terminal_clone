import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import type { TimeSeriesSeries } from '@/components/charts/TimeSeriesChart';

export interface NAVChartProps {
  series: { date: string; nav: number }[];
  height?: number;
}

export function NAVChart({ series, height = 320 }: NAVChartProps) {
  const data = series.map((pt) => ({ date: pt.date, value: pt.nav }));

  const highWaterMark = useMemo(
    () => Math.max(...series.map((pt) => pt.nav), 0),
    [series],
  );

  const chartSeries: TimeSeriesSeries[] = [
    {
      key: 'value',
      name: 'NAV',
      color: 'var(--color-accent-primary)',
      type: 'area',
    },
  ];

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  const hwmLabelStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    paddingBottom: 'var(--space-1)',
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={hwmLabelStyle}>
        <span
          style={{
            display: 'inline-block',
            width: '20px',
            height: '0',
            borderTop: '2px dashed var(--color-signal-warning)',
          }}
        />
        <span>
          High-Water Mark:{' '}
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--color-signal-warning)',
            }}
          >
            ${highWaterMark.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </span>
      </div>

      <TimeSeriesChart
        data={data as { date: string; value: number; [key: string]: unknown }[]}
        series={chartSeries}
        height={height}
        showGrid
        showTooltip
        benchmarkLine={{
          value: highWaterMark,
          label: 'HWM',
          color: 'var(--color-signal-warning)',
        }}
        yAxisFormat={(v) =>
          v >= 1_000_000
            ? `$${(v / 1_000_000).toFixed(1)}M`
            : v >= 1_000
            ? `$${(v / 1_000).toFixed(0)}K`
            : `$${v.toFixed(0)}`
        }
      />
    </div>
  );
}

export default NAVChart;
