import { TimeSeriesChart } from '@/components/charts';
import type { TimeSeriesSeries } from '@/components/charts';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CommodityPricePoint {
  date: string;
  price: number;
}

export interface CommodityPriceChartProps {
  data: CommodityPricePoint[];
  commodity: string;
  unit: string;
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const PRICE_SERIES: TimeSeriesSeries[] = [
  {
    key: 'price',
    name: 'Price',
    color: CHART_THEME.colors.series[0],
    type: 'area',
  },
];

export function CommodityPriceChart({
  data,
  commodity,
  unit,
  height = 280,
  className,
}: CommodityPriceChartProps) {
  return (
    <div className={className}>
      {/* Commodity label */}
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
          color: 'var(--color-text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: '4px',
        }}
      >
        {commodity} ({unit})
      </div>

      <TimeSeriesChart
        data={data.map((d) => ({ date: d.date, value: d.price, price: d.price }))}
        series={PRICE_SERIES}
        height={height}
        showGrid
        showTooltip
        showLegend={false}
        yAxisFormat={(v) => `${unit}${v.toLocaleString()}`}
      />
    </div>
  );
}
