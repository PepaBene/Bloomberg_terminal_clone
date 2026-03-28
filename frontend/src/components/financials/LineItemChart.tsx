import { useMemo } from 'react';
import clsx from 'clsx';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Cell,
} from 'recharts';
import { CHART_THEME } from '../charts/chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface LineItemDataPoint {
  period: string;
  value: number;
}

export interface LineItemChartProps {
  label: string;
  data: LineItemDataPoint[];
  format?: 'currency' | 'percentage' | 'number';
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatValue(v: number, format: 'currency' | 'percentage' | 'number'): string {
  if (format === 'currency') {
    if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    return `$${v.toLocaleString()}`;
  }
  if (format === 'percentage') return `${v.toFixed(1)}%`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return v.toLocaleString();
}

function computeCAGR(data: LineItemDataPoint[]): number | null {
  if (data.length < 2) return null;
  const first = data[data.length - 1]!.value; // oldest
  const last = data[0]!.value; // most recent
  if (first <= 0 || last <= 0) return null;
  const years = data.length - 1;
  return (Math.pow(last / first, 1 / years) - 1) * 100;
}

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  value?: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  fmt: 'currency' | 'percentage' | 'number';
}

function CustomTooltip({ active, payload, label, fmt }: CustomTooltipProps) {
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
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: CHART_THEME.fonts.data,
          fontSize: 12,
          color: CHART_THEME.colors.tooltip.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {formatValue(payload[0]!.value ?? 0, fmt)}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function LineItemChart({
  label,
  data,
  format = 'currency',
  className,
}: LineItemChartProps) {
  const cagr = useMemo(() => computeCAGR(data), [data]);

  return (
    <div
      className={clsx('terminal-panel flex flex-col gap-2', className)}
      style={{ maxWidth: 480 }}
    >
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h4
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-base)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            margin: 0,
          }}
        >
          {label}
        </h4>
        {cagr != null && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color:
                cagr >= 0
                  ? 'var(--color-signal-positive)'
                  : 'var(--color-signal-negative)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            CAGR: {cagr >= 0 ? '+' : ''}
            {cagr.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Bar chart */}
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={data}
          margin={{ top: 4, right: 8, bottom: 4, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={false}
          />
          <XAxis
            dataKey="period"
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 9,
            }}
            tickLine={false}
            axisLine={{ stroke: CHART_THEME.colors.grid }}
          />
          <YAxis
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 9,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatValue(v, format)}
            width={55}
          />
          <RechartsTooltip
            content={<CustomTooltip fmt={format} />}
            cursor={{ fill: CHART_THEME.colors.accentGlow }}
          />
          <Bar dataKey="value" name={label} radius={[2, 2, 0, 0]} maxBarSize={32}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.value >= 0
                    ? CHART_THEME.colors.accent
                    : CHART_THEME.colors.negative
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
