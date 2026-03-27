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
} from 'recharts';
import { CHART_THEME } from './chartTheme';

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
            content={<CustomTooltip yAxisFormat={yAxisFormat} />}
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
