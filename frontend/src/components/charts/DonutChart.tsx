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
}

/* ------------------------------------------------------------------ */
/*  Active sector shape — slight expansion + glow                     */
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
      {/* Glow ring */}
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
      {/* Expanded sector */}
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
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  name?: string;
  value?: number;
  payload?: DonutDataPoint;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  const item = payload[0];
  if (!item) return null;

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
          marginBottom: 2,
        }}
      >
        {item.name}
      </div>
      <div
        style={{
          fontFamily: CHART_THEME.fonts.data,
          fontSize: 13,
          color: CHART_THEME.colors.tooltip.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {item.value?.toLocaleString()}
      </div>
    </div>
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

  /* Attach default colors */
  const coloredData = useMemo(
    () => data.map((d, i) => ({ ...d, _fill: d.color ?? seriesColor(i) })),
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

        <RechartsTooltip content={<CustomTooltip />} />

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
