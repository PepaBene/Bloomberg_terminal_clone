import { useMemo } from 'react';
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
} from 'recharts';
import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface YieldCurvePoint {
  tenor: string;
  rate: number;
}

export interface YieldCurveChartProps {
  current: YieldCurvePoint[];
  prior?: YieldCurvePoint[];
  priorLabel?: string;
  height?: number;
  showSpread?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Custom active dot                                                  */
/* ------------------------------------------------------------------ */

interface ActiveDotProps {
  cx?: number;
  cy?: number;
  stroke?: string;
}

function ActiveDot({ cx = 0, cy = 0, stroke = CHART_THEME.colors.accent }: ActiveDotProps) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={7} fill={stroke} opacity={0.15} />
      <circle cx={cx} cy={cy} r={3.5} fill={stroke} stroke="#0C0F12" strokeWidth={1.5} />
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
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

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
      {payload.map((entry) => {
        if (entry.dataKey === 'spread' || entry.dataKey === 'inversionFill') return null;
        return (
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
              {entry.value != null ? `${entry.value.toFixed(2)}%` : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function YieldCurveChart({
  current,
  prior,
  priorLabel = 'Prior',
  height = 320,
  showSpread = true,
}: YieldCurveChartProps) {
  /*
   * Merge current and prior into a single data array keyed by tenor.
   * We also calculate spread and inversion fill areas.
   */
  const mergedData = useMemo(() => {
    const priorMap = new Map<string, number>();
    if (prior) {
      for (const p of prior) {
        priorMap.set(p.tenor, p.rate);
      }
    }

    return current.map((c) => {
      const priorRate = priorMap.get(c.tenor);
      const spread = priorRate != null ? c.rate - priorRate : undefined;

      // For inversion: check if current curve inverts by comparing to the
      // previous tenor. We mark segments where yield drops.
      return {
        tenor: c.tenor,
        current: c.rate,
        ...(priorRate != null ? { prior: priorRate } : {}),
        ...(spread != null ? { spread } : {}),
      };
    });
  }, [current, prior]);

  /*
   * Detect inversion regions: where a higher-tenor has a lower rate than
   * a shorter-tenor. We shade these red.
   */
  const inversionData = useMemo(() => {
    return mergedData.map((d, i) => {
      if (i === 0) return { ...d, inversionFill: undefined as number | undefined };
      const prev = mergedData[i - 1];
      const isInverted = prev != null && d.current < prev.current;
      return {
        ...d,
        inversionFill: isInverted ? d.current : undefined,
      };
    });
  }, [mergedData]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={inversionData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.colors.grid} vertical={false} />

        <XAxis
          dataKey="tenor"
          tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.ui, fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: CHART_THEME.colors.grid }}
        />

        <YAxis
          orientation="right"
          tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
          width={52}
        />

        <RechartsTooltip
          content={<CustomTooltip />}
          cursor={{ stroke: CHART_THEME.colors.accent, strokeWidth: 1, strokeDasharray: '3 3' }}
        />

        <Legend
          wrapperStyle={{
            fontFamily: CHART_THEME.fonts.ui,
            fontSize: 11,
            color: CHART_THEME.colors.textSecondary,
          }}
        />

        {/* Shaded spread area between curves (when prior exists) */}
        {prior && showSpread && (
          <>
            {/* The area between the two lines: fill the current line's area and
                layer the prior line's area to create a visual spread band. */}
            <Area
              type="monotone"
              dataKey="current"
              name="Current"
              stroke="none"
              fill={CHART_THEME.colors.accent}
              fillOpacity={0.08}
              legendType="none"
            />
          </>
        )}

        {/* Inversion shading: red tinted area where curve inverts */}
        <Area
          type="monotone"
          dataKey="inversionFill"
          name="Inversion"
          stroke="none"
          fill={CHART_THEME.colors.negative}
          fillOpacity={0.15}
          legendType="none"
          connectNulls={false}
        />

        {/* Prior curve — dashed, muted */}
        {prior && (
          <Line
            type="monotone"
            dataKey="prior"
            name={priorLabel}
            stroke={CHART_THEME.colors.textTertiary}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            activeDot={<ActiveDot stroke={CHART_THEME.colors.textTertiary} />}
          />
        )}

        {/* Current curve — solid accent with dots */}
        <Line
          type="monotone"
          dataKey="current"
          name="Current"
          stroke={CHART_THEME.colors.accent}
          strokeWidth={2}
          dot={{
            r: 3,
            fill: CHART_THEME.colors.accent,
            stroke: CHART_THEME.colors.surfaceBase,
            strokeWidth: 1.5,
          }}
          activeDot={<ActiveDot />}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
