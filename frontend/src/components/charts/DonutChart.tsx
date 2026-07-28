import { useMemo } from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend,
} from 'recharts';
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
}: DonutChartProps) {
  /* Compute radii relative to available space */
  const outerRadius = outerRadiusProp ?? Math.round(height * 0.38);
  const innerRadius = innerRadiusProp ?? Math.round(outerRadius * 0.6);

  /* Attach default colors */
  const coloredData = useMemo(
    () => data.map((d, i) => ({ ...d, _fill: d.color ?? seriesColor(i) })),
    [data],
  );

  /* Total for percentage calculation */
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
