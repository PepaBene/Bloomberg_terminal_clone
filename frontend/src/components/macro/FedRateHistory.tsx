import { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ReferenceDot,
} from 'recharts';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FedRatePoint {
  date: string;
  rate: number;
  decision?: 'HIKE' | 'CUT' | 'HOLD';
}

export interface FedRateHistoryProps {
  data: FedRatePoint[];
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const DECISION_COLOR: Record<string, string> = {
  CUT: CHART_THEME.colors.positive,
  HIKE: CHART_THEME.colors.negative,
  HOLD: CHART_THEME.colors.textSecondary,
};

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

interface RateTooltipProps {
  active?: boolean;
  payload?: { value?: number; payload?: FedRatePoint }[];
  label?: string;
}

function RateTooltip({ active, payload, label }: RateTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  return (
    <div
      style={{
        background: CHART_THEME.colors.tooltip.bg,
        border: `1px solid ${CHART_THEME.colors.tooltip.border}`,
        borderRadius: '4px',
        padding: '8px 12px',
        fontFamily: CHART_THEME.fonts.ui,
        fontSize: '11px',
        boxShadow: CHART_THEME.shadowFloat,
      }}
    >
      <div style={{ color: CHART_THEME.colors.tooltip.label, marginBottom: '4px' }}>
        {label}
      </div>
      <div
        style={{
          fontFamily: CHART_THEME.fonts.data,
          fontSize: '13px',
          color: CHART_THEME.colors.tooltip.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {point.rate.toFixed(2)}%
      </div>
      {point.decision && (
        <div
          style={{
            marginTop: '4px',
            fontSize: '10px',
            fontWeight: 600,
            color: DECISION_COLOR[point.decision] ?? CHART_THEME.colors.textSecondary,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          {point.decision}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function FedRateHistory({
  data,
  height = 320,
  className,
}: FedRateHistoryProps) {
  const decisionPoints = useMemo(
    () => data.filter((d) => d.decision != null),
    [data],
  );

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={false}
          />

          <XAxis
            dataKey="date"
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={{ stroke: CHART_THEME.colors.grid }}
          />

          <YAxis
            orientation="right"
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v.toFixed(2)}%`}
            width={60}
          />

          <RechartsTooltip
            content={<RateTooltip />}
            cursor={{
              stroke: CHART_THEME.colors.accent,
              strokeWidth: 1,
              strokeDasharray: '3 3',
            }}
          />

          {/* Step-line: rates don't interpolate */}
          <Area
            type="stepAfter"
            dataKey="rate"
            name="Fed Funds Rate"
            stroke={CHART_THEME.colors.accent}
            strokeWidth={1.5}
            fill={CHART_THEME.colors.accent}
            fillOpacity={0.1}
            dot={false}
          />

          {/* Decision dots */}
          {decisionPoints.map((dp) => (
            <ReferenceDot
              key={dp.date}
              x={dp.date}
              y={dp.rate}
              r={4}
              fill={DECISION_COLOR[dp.decision!] ?? CHART_THEME.colors.textSecondary}
              stroke={CHART_THEME.colors.surfaceBase}
              strokeWidth={1.5}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
