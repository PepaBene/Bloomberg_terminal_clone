import { useMemo } from 'react';
import {
  TimeSeriesChart,
  seriesColor,
} from '@/components/charts';
import type { TimeSeriesSeries } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ShortInterestDataPoint {
  date: string;
  shortInterest: number;
  daysToCover: number;
  shortPctFloat: number;
}

export interface ShortInterestChartProps {
  data: ShortInterestDataPoint[];
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ShortInterestChart({ data }: ShortInterestChartProps) {
  /* Map data into the shape TimeSeriesChart expects */
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: d.date,
        value: d.shortInterest,
        shortInterest: d.shortInterest,
        daysToCover: d.daysToCover,
        shortPctFloat: d.shortPctFloat,
      })),
    [data],
  );

  const series: TimeSeriesSeries[] = useMemo(
    () => [
      {
        key: 'shortInterest',
        name: 'Short Interest',
        color: seriesColor(4), // red-ish
        type: 'area' as const,
      },
      {
        key: 'daysToCover',
        name: 'Days to Cover',
        color: seriesColor(0), // blue
        type: 'line' as const,
      },
    ],
    [],
  );

  return (
    <div className="terminal-panel flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Short Interest
        </span>
        {data.length > 0 && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            % Float Short: {data[data.length - 1]?.shortPctFloat.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Chart */}
      <TimeSeriesChart
        data={chartData}
        series={series}
        height={280}
        showTooltip
        showGrid
        showLegend
        yAxisFormat={(v) => {
          if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
          if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
          return v.toFixed(1);
        }}
      />
    </div>
  );
}
