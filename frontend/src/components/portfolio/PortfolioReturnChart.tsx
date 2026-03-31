import type { CSSProperties } from 'react';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import type { TimeSeriesSeries } from '@/components/charts/TimeSeriesChart';

export interface PortfolioReturnChartProps {
  portfolioSeries: { date: string; value: number }[];
  benchmarkSeries?: { date: string; value: number }[];
  benchmarkLabel?: string;
  height?: number;
}

export function PortfolioReturnChart({
  portfolioSeries,
  benchmarkSeries,
  benchmarkLabel = 'Benchmark',
  height = 320,
}: PortfolioReturnChartProps) {
  // Merge portfolio and benchmark data by date
  const mergedData = portfolioSeries.map((pt) => {
    const bpt = benchmarkSeries?.find((b) => b.date === pt.date);
    return {
      date: pt.date,
      value: pt.value,
      benchmark: bpt?.value,
    };
  });

  const series: TimeSeriesSeries[] = [
    {
      key: 'value',
      name: 'Portfolio',
      color: 'var(--color-accent-primary)',
      type: 'area',
    },
  ];

  if (benchmarkSeries && benchmarkSeries.length > 0) {
    series.push({
      key: 'benchmark',
      name: benchmarkLabel,
      color: 'var(--color-chart-3)',
      type: 'line',
    });
  }

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  const legendStyle: CSSProperties = {
    display: 'flex',
    gap: 'var(--space-4)',
    paddingBottom: 'var(--space-2)',
  };

  const legendItemStyle = (_color: string, _dashed = false): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-secondary)',
  });

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={legendStyle}>
        <div style={legendItemStyle('var(--color-accent-primary)')}>
          <span
            style={{
              display: 'inline-block',
              width: '20px',
              height: '2px',
              background: 'var(--color-accent-primary)',
            }}
          />
          Portfolio
        </div>
        {benchmarkSeries && benchmarkSeries.length > 0 && (
          <div style={legendItemStyle('var(--color-chart-3)', true)}>
            <span
              style={{
                display: 'inline-block',
                width: '20px',
                height: '2px',
                background: 'var(--color-chart-3)',
                backgroundImage: `repeating-linear-gradient(
                  to right,
                  var(--color-chart-3) 0,
                  var(--color-chart-3) 5px,
                  transparent 5px,
                  transparent 9px
                )`,
                backgroundSize: '9px 2px',
              }}
            />
            {benchmarkLabel}
          </div>
        )}
      </div>

      <TimeSeriesChart
        data={mergedData as { date: string; value: number; [key: string]: unknown }[]}
        series={series}
        height={height}
        showGrid
        showTooltip
        yAxisFormat={(v) => `${v.toFixed(1)}%`}
      />
    </div>
  );
}

export default PortfolioReturnChart;
