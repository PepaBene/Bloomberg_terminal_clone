import { useMemo } from 'react';
import { TimeSeriesChart } from '@/components/charts';
import type { TimeSeriesSeries } from '@/components/charts';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface InflationDataPoint {
  date: string;
  headline: number;
  core: number;
  pce?: number;
}

export interface InflationChartProps {
  data: InflationDataPoint[];
  target?: number;
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function InflationChart({
  data,
  target = 2,
  height = 320,
  className,
}: InflationChartProps) {
  const hasPce = useMemo(
    () => data.some((d) => d.pce != null),
    [data],
  );

  const series = useMemo<TimeSeriesSeries[]>(() => {
    const s: TimeSeriesSeries[] = [
      { key: 'headline', name: 'Headline CPI', color: CHART_THEME.colors.series[0], type: 'area' },
      { key: 'core', name: 'Core CPI', color: CHART_THEME.colors.series[1], type: 'area' },
    ];
    if (hasPce) {
      s.push({ key: 'pce', name: 'PCE', color: CHART_THEME.colors.series[2], type: 'area' });
    }
    return s;
  }, [hasPce]);

  const benchmark = target != null
    ? { value: target, label: `${target}% Target` }
    : undefined;

  return (
    <div className={className}>
      <TimeSeriesChart
        data={data.map((d) => ({ ...d, date: d.date, value: d.headline } as { date: string; value: number; [key: string]: unknown }))}
        series={series}
        height={height}
        showGrid
        showTooltip
        showLegend
        yAxisFormat={(v) => `${v.toFixed(1)}%`}
        benchmarkLine={benchmark}
      />
    </div>
  );
}
