import { useMemo } from 'react';
import clsx from 'clsx';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  Tooltip as RechartsTooltip,
  Legend,
} from 'recharts';
import { CHART_THEME } from '../charts/chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface EquityCreditPoint {
  date: string;
  price: number;
  spread: number;
}

export interface EquityCreditDivergenceProps {
  data: EquityCreditPoint[];
  entityName: string;
  height?: number;
  className?: string;
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
        const formatted = `${(entry.value ?? 0) >= 100 ? '+' : ''}${((entry.value ?? 0) - 100).toFixed(1)}%`;

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
            <span
              style={{
                fontFamily: CHART_THEME.fonts.ui,
                color: CHART_THEME.colors.tooltip.label,
              }}
            >
              {entry.name}
            </span>
            <span style={{ marginLeft: 'auto', fontVariantNumeric: 'tabular-nums' }}>
              {formatted}
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

export function EquityCreditDivergence({
  data,
  entityName,
  height = 320,
  className,
}: EquityCreditDivergenceProps) {
  /* Index both series to 100 at the first observation so they share one
   * honest axis (see anti-patterns: two independently-scaled y-axes let
   * the visual "divergence" be an artifact of arbitrary scaling rather
   * than the real relationship). Also flags divergence periods: equity
   * up + spread widening, or equity down + spread tightening. */
  const enrichedData = useMemo(() => {
    if (data.length === 0) return [];
    const basePrice = data[0]!.price;
    const baseSpread = data[0]!.spread;

    return data.map((d, i) => {
      const priceIndex = basePrice ? (d.price / basePrice) * 100 : 100;
      const spreadIndex = baseSpread ? (d.spread / baseSpread) * 100 : 100;
      if (i === 0) return { ...d, priceIndex, spreadIndex, divergent: false };
      const prev = data[i - 1]!;
      const priceUp = d.price > prev.price;
      const spreadUp = d.spread > prev.spread;
      // Divergence = equity rallies while credit deteriorates, or vice versa
      const divergent = priceUp !== spreadUp;
      return { ...d, priceIndex, spreadIndex, divergent };
    });
  }, [data]);

  return (
    <div className={clsx('terminal-panel flex flex-col gap-2', className)}>
      <h3 className="terminal-section-title">
        Equity vs Credit — {entityName}
      </h3>

      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={enrichedData}
          margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
        >
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

          {/* Single axis: both series indexed to 100 at the first observation */}
          <YAxis
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}`}
            width={44}
            domain={['auto', 'auto']}
          />

          <ReferenceLine y={100} stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth={1} />

          <RechartsTooltip
            content={<CustomTooltip />}
            cursor={{
              stroke: CHART_THEME.colors.accent,
              strokeWidth: 1,
              strokeDasharray: '3 3',
            }}
          />

          <Legend
            wrapperStyle={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 11,
              color: CHART_THEME.colors.textSecondary,
            }}
          />

          {/* Equity price, indexed to 100 at the first observation */}
          <Line
            type="monotone"
            dataKey="priceIndex"
            name="Stock Price (Indexed)"
            stroke={CHART_THEME.colors.positive}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 4, fill: CHART_THEME.colors.positive, stroke: '#0C0F12', strokeWidth: 1.5 }}
          />

          {/* Credit OAS spread, indexed to 100 at the first observation */}
          <Line
            type="monotone"
            dataKey="spreadIndex"
            name="OAS Spread (Indexed)"
            stroke={CHART_THEME.colors.negative}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 4, fill: CHART_THEME.colors.negative, stroke: '#0C0F12', strokeWidth: 1.5 }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
          paddingTop: 2,
        }}
      >
        Both series indexed to 100 at the start of the window so they share one honest scale — a widening gap is real divergence, not an axis artifact. Rising spread = deteriorating credit quality.
      </div>
    </div>
  );
}
