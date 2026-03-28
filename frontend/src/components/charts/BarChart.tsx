import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  Cell,
  ReferenceLine,
} from 'recharts';
import { CHART_THEME } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';
import type { ChartTooltipSeriesItem, ChartTooltipChange } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface BarDefinition {
  key: string;
  color: string;
  name: string;
  stackId?: string;
}

export interface BarChartComponentProps {
  data: Record<string, unknown>[];
  bars: BarDefinition[];
  xKey: string;
  height?: number;
  layout?: 'vertical' | 'horizontal';
  showGrid?: boolean;
  showTooltip?: boolean;
  showLegend?: boolean;
  yAxisFormat?: (v: number) => string;
  /** Show a thin horizontal reference line at the period mean */
  showMeanLine?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Rich tooltip using ChartTooltip                                    */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string;
  payload?: Record<string, unknown>;
}

interface RichBarTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  yAxisFormat?: (v: number) => string;
  allData?: Record<string, unknown>[];
}

function RichBarTooltip({ active, payload, label, yAxisFormat, allData }: RichBarTooltipProps) {
  if (!active || !payload?.length) return null;

  const fmt = yAxisFormat ?? ((v: number) => v.toLocaleString());

  const firstEntry = payload[0];
  const primaryValue = firstEntry?.value != null ? fmt(firstEntry.value) : '\u2014';

  // Compute period-over-period change if data supports it
  let change: ChartTooltipChange | undefined;
  if (allData && label && firstEntry?.dataKey) {
    const currentIdx = allData.findIndex((d) => d[Object.keys(d)[0] ?? ''] === label);
    if (currentIdx > 0) {
      const priorRow = allData[currentIdx - 1];
      const priorVal = priorRow?.[firstEntry.dataKey as string];
      if (firstEntry.value != null && typeof priorVal === 'number' && priorVal !== 0) {
        const pctChange = ((firstEntry.value - priorVal) / Math.abs(priorVal)) * 100;
        change = {
          value: `${Math.abs(pctChange).toFixed(1)}%`,
          direction: pctChange > 0 ? 'up' : pctChange < 0 ? 'down' : 'flat',
          period: 'PoP',
        };
      }
    }
  }

  // Build series list for multi-bar display
  const seriesItems: ChartTooltipSeriesItem[] = payload.map((entry) => ({
    name: entry.name ?? String(entry.dataKey ?? ''),
    value: entry.value != null ? fmt(entry.value) : '\u2014',
    color: entry.color ?? CHART_THEME.colors.accent,
  }));

  return (
    <ChartTooltip
      title={String(label ?? '')}
      value={primaryValue}
      change={change}
      series={seriesItems.length > 1 ? seriesItems : undefined}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BarChartComponent({
  data,
  bars,
  xKey,
  height = 320,
  layout = 'horizontal',
  showGrid = true,
  showTooltip = true,
  showLegend = false,
  yAxisFormat,
  showMeanLine = true,
}: BarChartComponentProps) {
  const isVertical = layout === 'vertical';

  /**
   * For horizontal bars the category axis is X and value axis is Y.
   * For vertical layout (horizontal bars) the axes are swapped.
   */
  const categoryAxisProps = useMemo(
    () => ({
      dataKey: xKey,
      tick: { fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.ui, fontSize: 10 },
      tickLine: false,
      axisLine: { stroke: CHART_THEME.colors.grid },
    }),
    [xKey],
  );

  const valueAxisProps = useMemo(
    () => ({
      tick: { fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 },
      tickLine: false,
      axisLine: false,
      tickFormatter: yAxisFormat,
    }),
    [yAxisFormat],
  );

  /**
   * Compute the mean of the first bar's values for the reference line.
   */
  const meanValue = useMemo(() => {
    if (!showMeanLine || bars.length === 0) return undefined;
    const key = bars[0]!.key;
    const values = data
      .map((d) => d[key])
      .filter((v): v is number => typeof v === 'number');
    if (values.length === 0) return undefined;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }, [data, bars, showMeanLine]);

  /**
   * Check if any value is negative for zero baseline emphasis.
   */
  const hasNegativeValues = useMemo(() => {
    return bars.some((b) =>
      data.some((d) => {
        const v = d[b.key];
        return typeof v === 'number' && v < 0;
      }),
    );
  }, [data, bars]);

  const fmt = yAxisFormat ?? ((v: number) => v.toLocaleString());

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBarChart
        data={data}
        layout={isVertical ? 'vertical' : 'horizontal'}
        margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
      >
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={!isVertical}
            horizontal={isVertical}
          />
        )}

        {isVertical ? (
          <>
            <YAxis type="category" {...categoryAxisProps} width={80} />
            <XAxis type="number" {...valueAxisProps} />
          </>
        ) : (
          <>
            <XAxis type="category" {...categoryAxisProps} />
            <YAxis type="number" {...valueAxisProps} width={60} />
          </>
        )}

        {showTooltip && (
          <RechartsTooltip
            content={<RichBarTooltip yAxisFormat={yAxisFormat} allData={data} />}
            cursor={{ fill: CHART_THEME.colors.accentGlow }}
          />
        )}

        {showLegend && (
          <Legend
            wrapperStyle={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 11,
              color: CHART_THEME.colors.textSecondary,
            }}
          />
        )}

        {/* Zero baseline emphasis for negative values */}
        {hasNegativeValues && !isVertical && (
          <ReferenceLine
            y={0}
            stroke={CHART_THEME.colors.surfaceBorderStrong}
            strokeWidth={1.5}
          />
        )}
        {hasNegativeValues && isVertical && (
          <ReferenceLine
            x={0}
            stroke={CHART_THEME.colors.surfaceBorderStrong}
            strokeWidth={1.5}
          />
        )}

        {/* Mean reference line — thin horizontal line at period mean */}
        {meanValue != null && !isVertical && (
          <ReferenceLine
            y={meanValue}
            stroke={CHART_THEME.colors.textSecondary}
            strokeDasharray="4 3"
            strokeWidth={1}
            label={{
              value: `Mean: ${fmt(meanValue)}`,
              fill: CHART_THEME.colors.textSecondary,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 9,
              position: 'insideTopRight',
            }}
          />
        )}

        {bars.map((b) => (
          <Bar
            key={b.key}
            dataKey={b.key}
            name={b.name}
            stackId={b.stackId}
            radius={[2, 2, 0, 0]}
            maxBarSize={48}
          >
            {data.map((_entry, i) => (
              <Cell key={i} fill={b.color} />
            ))}
          </Bar>
        ))}
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
