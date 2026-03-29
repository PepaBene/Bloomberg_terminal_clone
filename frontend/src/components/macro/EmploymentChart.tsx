import { BarChartComponent, TimeSeriesChart } from '@/components/charts';
import type { BarDefinition, TimeSeriesSeries } from '@/components/charts';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface NFPDataPoint {
  date: string;
  actual: number;
  forecast: number;
}

export interface UnemploymentDataPoint {
  date: string;
  rate: number;
}

export interface EmploymentChartProps {
  nfpData: NFPDataPoint[];
  unemploymentData: UnemploymentDataPoint[];
  nfpHeight?: number;
  unemploymentHeight?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const NFP_BARS: BarDefinition[] = [
  { key: 'actual', name: 'Actual', color: CHART_THEME.colors.series[0] },
  { key: 'forecast', name: 'Forecast', color: CHART_THEME.colors.series[2] },
];

const UNEMP_SERIES: TimeSeriesSeries[] = [
  {
    key: 'rate',
    name: 'Unemployment Rate',
    color: CHART_THEME.colors.series[4],
    type: 'area',
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function EmploymentChart({
  nfpData,
  unemploymentData,
  nfpHeight = 240,
  unemploymentHeight = 200,
  className,
}: EmploymentChartProps) {
  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* NFP bar chart */}
      <div>
        <h4
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
          Non-Farm Payrolls (K)
        </h4>
        <BarChartComponent
          data={nfpData as unknown as Record<string, unknown>[]}
          bars={NFP_BARS}
          xKey="date"
          height={nfpHeight}
          showGrid
          showTooltip
          showLegend
          showMeanLine
          yAxisFormat={(v) => `${(v / 1000).toFixed(0)}K`}
        />
      </div>

      {/* Unemployment rate line chart */}
      <div>
        <h4
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
          Unemployment Rate
        </h4>
        <TimeSeriesChart
          data={unemploymentData.map((d) => ({ ...d, value: d.rate }))}
          series={UNEMP_SERIES}
          height={unemploymentHeight}
          showGrid
          showTooltip
          showLegend={false}
          yAxisFormat={(v) => `${v.toFixed(1)}%`}
        />
      </div>
    </div>
  );
}
