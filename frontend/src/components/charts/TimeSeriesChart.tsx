import { useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
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
/*  Custom active-dot with accent glow                                */
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
      <circle cx={cx} cy={cy} r={4} fill={stroke} stroke="#0C0F12" strokeWidth={1.5} />
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  yAxisFormat?: (v: number) => string;
}

function CustomTooltip({ active, payload, label, yAxisFormat }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  const fmt = yAxisFormat ?? ((v: number) => v.toLocaleString());

  return (
    <div
      style={{
        background: CHART_THEME.colors.tooltip.bg,
        border: `1px solid ${CHART_THEME.colors.tooltip.border}`,
        borderRadius: 4,
        padding: '8px 12px',
        boxShadow: CHART_THEME.shadowFloat,
      }}
    >
      <div
        style={{
          fontFamily: CHART_THEME.fonts.ui,
          fontSize: 11,
          color: CHART_THEME.colors.tooltip.label,
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      {payload.map((entry) => (
        <div
          key={entry.dataKey ?? entry.name}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: CHART_THEME.fonts.data,
            fontSize: 12,
            color: CHART_THEME.colors.tooltip.text,
            lineHeight: 1.6,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: entry.color,
              flexShrink: 0,
            }}
          />
          <span style={{ fontFamily: CHART_THEME.fonts.ui, color: CHART_THEME.colors.tooltip.label }}>
            {entry.name}
          </span>
          <span style={{ marginLeft: 'auto', fontVariantNumeric: 'tabular-nums' }}>
            {entry.value != null ? fmt(entry.value) : '—'}
          </span>
        </div>
      ))}
    </div>
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
        : [{ key: 'value', color: seriesColor(0), name: 'Value', type: 'line' as const }],
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
            content={<CustomTooltip yAxisFormat={yAxisFormat} />}
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
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={1.5}
              dot={false}
              activeDot={<ActiveDot stroke={s.color} />}
            />
          ),
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
