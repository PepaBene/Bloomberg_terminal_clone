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
  ReferenceLine,
  Cell,
} from 'recharts';
import { CHART_THEME } from '../charts/chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MaturityBucket {
  year: number;
  amount: number;
  isHighYield?: boolean;
}

export interface MaturityWallChartProps {
  maturities: MaturityBucket[];
  totalDebt: number;
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  name?: string;
  value?: number;
  payload?: MaturityBucket;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const entry = payload[0]!;
  const bucket = entry.payload;

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
      <div
        style={{
          fontFamily: CHART_THEME.fonts.data,
          fontSize: 12,
          color: CHART_THEME.colors.tooltip.text,
        }}
      >
        ${(entry.value ?? 0).toFixed(0)}M
        {bucket?.isHighYield && (
          <span
            style={{
              marginLeft: 6,
              color: CHART_THEME.colors.warning,
              fontSize: 10,
            }}
          >
            HY
          </span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtMoney(n: number): string {
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(1)}B`;
  return `$${n.toFixed(0)}M`;
}

function fmtYAxis(v: number): string {
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}B`;
  return `${v}M`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function MaturityWallChart({
  maturities,
  totalDebt,
  height = 300,
  className,
}: MaturityWallChartProps) {
  const avgAnnual = useMemo(() => {
    if (maturities.length === 0) return 0;
    const total = maturities.reduce((s, m) => s + m.amount, 0);
    return total / maturities.length;
  }, [maturities]);

  const chartData = useMemo(
    () => maturities.map((m) => ({ ...m, name: String(m.year) })),
    [maturities],
  );

  return (
    <div className={clsx('terminal-panel flex flex-col gap-2', className)}>
      <div className="flex items-baseline justify-between">
        <h3 className="terminal-section-title" style={{ margin: 0 }}>
          Maturity Wall
        </h3>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          Total Debt: {fmtMoney(totalDebt)}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chartData}
          margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={false}
          />
          <XAxis
            dataKey="name"
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={{ stroke: CHART_THEME.colors.grid }}
          />
          <YAxis
            tick={{
              fill: CHART_THEME.colors.axis,
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={fmtYAxis}
            width={60}
          />
          <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: CHART_THEME.colors.accentGlow }} />

          {/* Average annual maturity reference line */}
          {avgAnnual > 0 && (
            <ReferenceLine
              y={avgAnnual}
              label={{
                value: `Avg: $${avgAnnual.toFixed(0)}M`,
                fill: CHART_THEME.colors.neutral,
                fontFamily: CHART_THEME.fonts.ui,
                fontSize: 10,
                position: 'insideTopRight',
              }}
              stroke={CHART_THEME.colors.neutral}
              strokeDasharray="6 3"
              strokeWidth={1}
            />
          )}

          <Bar dataKey="amount" name="Maturing Debt" radius={[2, 2, 0, 0]} maxBarSize={48}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.isHighYield
                    ? CHART_THEME.colors.warning
                    : CHART_THEME.colors.accent
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
