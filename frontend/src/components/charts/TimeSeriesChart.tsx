import { useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import type { CategoricalChartState } from 'recharts/types/chart/types';
import { CHART_THEME, seriesColor } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';
import type { ChartTooltipSeriesItem } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface TimeSeriesSeries {
  key: string;
  color: string;
  name: string;
  type?: 'line' | 'area';
}

export interface TimeSeriesEvent {
  date: string;
  label: string;
  type: string;
}

export interface TimeSeriesChartProps {
  data: { date: string; value: number; [key: string]: unknown }[];
  series?: TimeSeriesSeries[];
  height?: number;
  showGrid?: boolean;
  showTooltip?: boolean;
  showLegend?: boolean;
  yAxisFormat?: (v: number) => string;
  xAxisFormat?: (v: string) => string;
  onPointClick?: (point: unknown) => void;
  benchmarkLine?: { value: number; label: string; color?: string };
  events?: TimeSeriesEvent[];
}

/* ------------------------------------------------------------------ */
/*  Custom active-dot with accent glow (3px, only on hover)           */
/* ------------------------------------------------------------------ */

interface ActiveDotProps {
  cx?: number;
  cy?: number;
  stroke?: string;
}

function ActiveDot({ cx = 0, cy = 0, stroke = CHART_THEME.colors.accent }: ActiveDotProps) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill={stroke} opacity={0.15} />
      <circle cx={cx} cy={cy} r={3} fill={stroke} stroke="#0C0F12" strokeWidth={1.5} />
    </g>
  );
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

interface RichTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  yAxisFormat?: (v: number) => string;
  benchmarkLine?: { value: number; label: string; color?: string };
  allData?: { date: string; value: number; [key: string]: unknown }[];
}

function RichTooltip({ active, payload, label, yAxisFormat, benchmarkLine, allData }: RichTooltipProps) {
  if (!active || !payload?.length) return null;

  const fmt = yAxisFormat ?? ((v: number) => v.toLocaleString());

  // Build primary value from first entry
  const firstEntry = payload[0];
  const primaryValue = firstEntry?.value != null ? fmt(firstEntry.value) : '\u2014';

  // Compute YoY change if prior data exists
  let change: { value: string; direction: 'up' | 'down' | 'flat'; period: string } | undefined;
  if (allData && label && firstEntry?.dataKey) {
    const currentIdx = allData.findIndex((d) => d.date === label);
    if (currentIdx > 0) {
      const currentVal = firstEntry.value;
      const priorPoint = allData[currentIdx - 1];
      const priorVal = priorPoint?.[firstEntry.dataKey as string];
      if (currentVal != null && typeof priorVal === 'number' && priorVal !== 0) {
        const pctChange = ((currentVal - priorVal) / Math.abs(priorVal)) * 100;
        const dir = pctChange > 0 ? 'up' : pctChange < 0 ? 'down' : 'flat';
        change = {
          value: `${Math.abs(pctChange).toFixed(1)}%`,
          direction: dir as 'up' | 'down' | 'flat',
          period: 'YoY',
        };
      }
    }
  }

  // Build benchmark prop
  const benchmark = benchmarkLine
    ? { label: benchmarkLine.label, value: fmt(benchmarkLine.value) }
    : undefined;

  // Build series list for multi-series
  let seriesItems: ChartTooltipSeriesItem[] | undefined;
  if (payload.length > 1) {
    seriesItems = payload.map((entry) => ({
      name: entry.name ?? String(entry.dataKey ?? ''),
      value: entry.value != null ? fmt(entry.value) : '\u2014',
      color: entry.color ?? CHART_THEME.colors.accent,
    }));
  }

  return (
    <ChartTooltip
      title={label ?? ''}
      value={primaryValue}
      change={change}
      benchmark={benchmark}
      series={seriesItems}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Event marker (small triangle on x-axis)                           */
/* ------------------------------------------------------------------ */

interface EventTickProps {
  x?: number;
  y?: number;
  payload?: { value?: string };
  events: TimeSeriesEvent[];
}

function EventTick({ x = 0, y = 0, payload, events }: EventTickProps) {
  const ev = events.find((e) => e.date === payload?.value);
  if (!ev) return <g />;

  const colorMap: Record<string, string> = {
    earnings: CHART_THEME.colors.highlight,
    filing: CHART_THEME.colors.textSecondary,
    dividend: CHART_THEME.colors.positive,
    management: CHART_THEME.colors.textSecondary,
    ma: CHART_THEME.colors.accent,
    analyst: CHART_THEME.colors.warning,
    macro: CHART_THEME.colors.neutral,
  };

  const fill = colorMap[ev.type] ?? CHART_THEME.colors.textTertiary;

  return (
    <g>
      <polygon
        points={`${x},${y + 6} ${x - 4},${y + 14} ${x + 4},${y + 14}`}
        fill={fill}
        opacity={0.85}
      />
      <title>{ev.label}</title>
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function TimeSeriesChart({
  data,
  series,
  height = 320,
  showGrid = true,
  showTooltip = true,
  showLegend = false,
  yAxisFormat,
  xAxisFormat,
  onPointClick,
  benchmarkLine,
  events,
}: TimeSeriesChartProps) {
  /* Resolve series definitions: if none provided, fall back to a single "value" series */
  const resolvedSeries = useMemo<TimeSeriesSeries[]>(
    () =>
      series && series.length > 0
        ? series
        : [{ key: 'value', color: seriesColor(0), name: 'Value', type: 'area' as const }],
    [series],
  );

  const handleClick = useCallback(
    (state: CategoricalChartState) => {
      if (onPointClick && state?.activePayload?.[0]) {
        onPointClick(state.activePayload[0].payload as unknown);
      }
    },
    [onPointClick],
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} onClick={handleClick} margin={{ top: 8, right: 12, bottom: events?.length ? 18 : 4, left: 4 }}>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={false}
          />
        )}

        <XAxis
          dataKey="date"
          tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.ui, fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: CHART_THEME.colors.grid }}
          tickFormatter={xAxisFormat}
        />

        {/* Event tick layer */}
        {events && events.length > 0 && (
          <XAxis
            dataKey="date"
            xAxisId="events"
            tick={(props: Record<string, unknown>) => (
              <EventTick {...(props as unknown as EventTickProps)} events={events} />
            )}
            tickLine={false}
            axisLine={false}
            orientation="bottom"
            height={18}
          />
        )}

        {/* Y-axis on the right side — analyst convention (spec 5.1.2) */}
        <YAxis
          orientation="right"
          tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={yAxisFormat}
          width={60}
        />

        {showTooltip && (
          <RechartsTooltip
            content={
              <RichTooltip
                yAxisFormat={yAxisFormat}
                benchmarkLine={benchmarkLine}
                allData={data}
              />
            }
            cursor={{ stroke: CHART_THEME.colors.accent, strokeWidth: 1, strokeDasharray: '3 3' }}
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

        {benchmarkLine && (
          <ReferenceLine
            y={benchmarkLine.value}
            label={{
              value: benchmarkLine.label,
              fill: benchmarkLine.color ?? CHART_THEME.colors.neutral,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
              position: 'insideTopRight',
            }}
            stroke={benchmarkLine.color ?? CHART_THEME.colors.neutral}
            strokeDasharray="6 3"
            strokeWidth={1}
          />
        )}

        {resolvedSeries.map((s) =>
          s.type === 'area' ? (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={1.5}
              fill={s.color}
              fillOpacity={0.15}
              dot={false}
              activeDot={<ActiveDot stroke={s.color} />}
            />
          ) : (
            /* Line series: render as area with 15% fill for gradient effect */
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={1.5}
              fill={s.color}
              fillOpacity={0.15}
              dot={false}
              activeDot={<ActiveDot stroke={s.color} />}
            />
          ),
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
