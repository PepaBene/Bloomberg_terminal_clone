import { useState, useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend,
  Sector,
} from 'recharts';
import type { PieSectorDataItem } from 'recharts/types/polar/Pie';
import { CHART_THEME, seriesColor } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DonutDataPoint {
  name: string;
  value: number;
  color?: string;
}

export interface DonutChartProps {
  data: DonutDataPoint[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string;
  showLegend?: boolean;
  /**
   * Max number of named slices before the rest fold into a single "Other"
   * slice. A pie/donut only reads at a glance up to ~6-7 segments, and the
   * 8-color categorical palette collides (wraps via modulo) past 8 — so an
   * uncapped donut both stops being legible and silently merges two
   * different categories into the same color. Default 6.
   */
  topN?: number;
}

/* ------------------------------------------------------------------ */
/*  Active sector shape — expansion + accent glow                     */
/* ------------------------------------------------------------------ */

interface ActiveShapeProps extends PieSectorDataItem {
  fill?: string;
}

function renderActiveShape(props: ActiveShapeProps) {
  const {
    cx = 0,
    cy = 0,
    innerRadius = 0,
    outerRadius = 0,
    startAngle = 0,
    endAngle = 0,
    fill = CHART_THEME.colors.accent,
  } = props;

  return (
    <g>
      {/* Accent glow ring */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.2}
      />
      {/* Expanded sector (+4px outerRadius) */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 4}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Rich tooltip using ChartTooltip                                    */
/* ------------------------------------------------------------------ */

interface DonutTooltipPayloadEntry {
  name?: string;
  value?: number;
  payload?: DonutDataPoint & { _fill?: string };
}

interface RichDonutTooltipProps {
  active?: boolean;
  payload?: DonutTooltipPayloadEntry[];
  totalValue?: number;
}

function RichDonutTooltip({ active, payload, totalValue }: RichDonutTooltipProps) {
  if (!active || !payload?.length) return null;

  const item = payload[0];
  if (!item) return null;

  const segmentValue = item.value ?? 0;
  const percentage = totalValue && totalValue > 0
    ? ((segmentValue / totalValue) * 100).toFixed(1)
    : null;
  const segmentColor = item.payload?._fill ?? item.payload?.color ?? CHART_THEME.colors.accent;

  return (
    <ChartTooltip
      title={item.name ?? ''}
      value={segmentValue.toLocaleString()}
      series={[
        {
          name: item.name ?? '',
          value: percentage ? `${segmentValue.toLocaleString()} (${percentage}%)` : segmentValue.toLocaleString(),
          color: segmentColor,
        },
      ]}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DonutChart({
  data,
  height = 300,
  innerRadius: innerRadiusProp,
  outerRadius: outerRadiusProp,
  centerLabel,
  centerValue,
  showLegend = false,
  topN = 6,
}: DonutChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | undefined>(undefined);

  const onEnter = useCallback((_: unknown, index: number) => {
    setActiveIndex(index);
  }, []);

  const onLeave = useCallback(() => {
    setActiveIndex(undefined);
  }, []);

  /* Compute radii relative to available space */
  const outerRadius = outerRadiusProp ?? Math.round(height * 0.38);
  const innerRadius = innerRadiusProp ?? Math.round(outerRadius * 0.6);

  /* Cap visible slices at topN, folding the remainder into a single
   * "Other" slice (neutral gray — it isn't one identity, so it doesn't
   * take a categorical color) rather than letting the palette wrap. */
  const cappedData = useMemo(() => {
    if (data.length <= topN) return data;
    const sorted = [...data].sort((a, b) => b.value - a.value);
    const shown = sorted.slice(0, topN);
    const rest = sorted.slice(topN);
    const otherValue = rest.reduce((sum, d) => sum + d.value, 0);
    return otherValue > 0 ? [...shown, { name: 'Other', value: otherValue, color: CHART_THEME.colors.textTertiary }] : shown;
  }, [data, topN]);

  /* Attach default colors */
  const coloredData = useMemo(
    () => cappedData.map((d, i) => ({ ...d, _fill: d.color ?? seriesColor(i) })),
    [cappedData],
  );

  /* Total for percentage calculation (all original data, so "Other" reads as its true share) */
  const totalValue = useMemo(
    () => data.reduce((sum, d) => sum + d.value, 0),
    [data],
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={coloredData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={innerRadius}
          outerRadius={outerRadius}
          paddingAngle={1}
          activeIndex={activeIndex}
          activeShape={renderActiveShape}
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
          stroke={CHART_THEME.colors.surfaceBase}
          strokeWidth={2}
        >
          {coloredData.map((entry, i) => (
            <Cell key={i} fill={entry._fill} />
          ))}
        </Pie>

        <RechartsTooltip content={<RichDonutTooltip totalValue={totalValue} />} />

        {showLegend && (
          <Legend
            wrapperStyle={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 11,
              color: CHART_THEME.colors.textSecondary,
            }}
          />
        )}

        {/* Center label + value — rendered as SVG text elements */}
        {(centerLabel || centerValue) && (
          <text
            x="50%"
            y="50%"
            textAnchor="middle"
            dominantBaseline="central"
          >
            {centerValue && (
              <tspan
                x="50%"
                dy={centerLabel ? '-0.4em' : '0'}
                style={{
                  fontFamily: CHART_THEME.fonts.data,
                  fontSize: 20,
                  fontWeight: 600,
                  fill: CHART_THEME.colors.textPrimary,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {centerValue}
              </tspan>
            )}
            {centerLabel && (
              <tspan
                x="50%"
                dy={centerValue ? '1.4em' : '0'}
                style={{
                  fontFamily: CHART_THEME.fonts.ui,
                  fontSize: 11,
                  fill: CHART_THEME.colors.textSecondary,
                }}
              >
                {centerLabel}
              </tspan>
            )}
          </text>
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}
