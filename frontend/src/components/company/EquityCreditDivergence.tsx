import { useMemo } from 'react';
import clsx from 'clsx';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
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
        const isPriceSeries = entry.dataKey === 'price';
        const formatted = isPriceSeries
          ? `$${(entry.value ?? 0).toFixed(2)}`
          : `${(entry.value ?? 0).toFixed(0)} bps`;

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
  /* Detect divergence periods: equity up + spread widening or equity down + spread tightening */
  const enrichedData = useMemo(() => {
    if (data.length < 2) return data;

    return data.map((d, i) => {
      if (i === 0) return { ...d, divergent: false };
      const prev = data[i - 1]!;
      const priceUp = d.price > prev.price;
      const spreadUp = d.spread > prev.spread;
      // Divergence = equity rallies while credit deteriorates, or vice versa
      const divergent = priceUp !== spreadUp;
      return { ...d, divergent };
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

          {/* Left axis: Stock price */}
          <YAxis
            yAxisId="price"
            orientation="left"
            tick={{
              fill: CHART_THEME.colors.positive,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            width={60}
          />

          {/* Right axis: OAS spread (inverted conceptually — higher = worse) */}
          <YAxis
            yAxisId="spread"
            orientation="right"
            tick={{
              fill: CHART_THEME.colors.negative,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}bp`}
            width={60}
            reversed
          />

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

          {/* Equity price line */}
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="price"
            name="Stock Price ($)"
            stroke={CHART_THEME.colors.positive}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 4, fill: CHART_THEME.colors.positive, stroke: '#0C0F12', strokeWidth: 1.5 }}
          />

          {/* Credit spread line */}
          <Line
            yAxisId="spread"
            type="monotone"
            dataKey="spread"
            name="OAS Spread (bps)"
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
        Spread axis inverted: lower = better credit quality. Divergence periods indicate equity/credit dislocation.
      </div>
    </div>
  );
}
