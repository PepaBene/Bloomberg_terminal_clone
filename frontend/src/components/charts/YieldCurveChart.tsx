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
import { ChartTooltip } from './ChartTooltip';
import type { ChartTooltipChange, ChartTooltipSeriesItem } from './ChartTooltip';

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
}

interface RichYieldTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  priorLabel?: string;
}

function RichYieldTooltip({ active, payload, label, priorLabel }: RichYieldTooltipProps) {
  if (!active || !payload?.length) return null;

  // Extract current and prior rates from the payload
  const currentEntry = payload.find((e) => e.dataKey === 'current');
  const priorEntry = payload.find((e) => e.dataKey === 'prior');

  const currentRate = currentEntry?.value;
  const priorRate = priorEntry?.value;

  const primaryValue = currentRate != null ? `${currentRate.toFixed(2)}%` : '\u2014';

  // Compute change between current and prior
  let change: ChartTooltipChange | undefined;
  if (currentRate != null && priorRate != null) {
    const diff = currentRate - priorRate;
    change = {
      value: `${Math.abs(diff).toFixed(2)}%`,
      direction: diff > 0 ? 'up' : diff < 0 ? 'down' : 'flat',
      period: 'vs ' + (priorLabel ?? 'Prior'),
    };
  }

  // Build series items showing both curves
  const seriesItems: ChartTooltipSeriesItem[] = [];
  if (currentEntry) {
    seriesItems.push({
      name: 'Current',
      value: currentRate != null ? `${currentRate.toFixed(2)}%` : '\u2014',
      color: CHART_THEME.colors.accent,
    });
  }
  if (priorEntry) {
    seriesItems.push({
      name: priorLabel ?? 'Prior',
      value: priorRate != null ? `${priorRate.toFixed(2)}%` : '\u2014',
      color: CHART_THEME.colors.textTertiary,
    });
  }

  // Show spread if both curves present
  let benchmark: { label: string; value: string } | undefined;
  if (currentRate != null && priorRate != null) {
    const spread = currentRate - priorRate;
    benchmark = {
      label: 'Spread',
      value: `${spread >= 0 ? '+' : ''}${spread.toFixed(2)}%`,
    };
  }

  return (
    <ChartTooltip
      title={`Tenor: ${label ?? ''}`}
      value={primaryValue}
      change={change}
      series={seriesItems.length > 1 ? seriesItems : undefined}
      benchmark={benchmark}
    />
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
   * a shorter-tenor. We shade these signal-negative at 15% opacity.
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
          content={<RichYieldTooltip priorLabel={priorLabel} />}
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
          <Area
            type="monotone"
            dataKey="current"
            name="Current"
            stroke="none"
            fill={CHART_THEME.colors.accent}
            fillOpacity={0.08}
            legendType="none"
          />
        )}

        {/* Inversion shading: signal-negative at 15% opacity */}
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

        {/* Current curve — solid accent with dots on hover only */}
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
