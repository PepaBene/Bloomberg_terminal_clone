import { useMemo } from 'react';
import { BarChartComponent } from '@/components/charts';
import type { BarDefinition } from '@/components/charts';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface GDPDataPoint {
  country: string;
  actual: number;
  forecast: number;
  prior: number;
}

export interface GDPChartProps {
  data: GDPDataPoint[];
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const BARS: BarDefinition[] = [
  { key: 'actual', name: 'Actual', color: CHART_THEME.colors.series[0] },
  { key: 'forecast', name: 'Forecast', color: CHART_THEME.colors.series[1] },
  { key: 'prior', name: 'Prior', color: CHART_THEME.colors.series[2] },
];

export function GDPChart({ data, height = 320, className }: GDPChartProps) {
  /** Sort countries by actual GDP descending */
  const sorted = useMemo(
    () => [...data].sort((a, b) => b.actual - a.actual),
    [data],
  );

  return (
    <div className={className}>
      <BarChartComponent
        data={sorted as unknown as Record<string, unknown>[]}
        bars={BARS}
        xKey="country"
        height={height}
        showGrid
        showTooltip
        showLegend
        showMeanLine={false}
        yAxisFormat={(v) => `${v.toFixed(1)}%`}
      />
    </div>
  );
}
