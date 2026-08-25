import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  LabelList,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { ChartTooltip } from '../charts/ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FactorBeta {
  name: string;
  /** The diverging value plotted — a raw beta, or an active tilt vs benchmark */
  beta: number;
  /** Optional context value shown in the tooltip (e.g. benchmark exposure) */
  benchmark?: number;
  /** Optional t-statistic; when omitted, significance styling is skipped */
  tStat?: number;
  /** Defaults to true when tStat is not supplied */
  significant?: boolean;
}

export interface FactorExposureChartProps {
  factors: FactorBeta[];
  height?: number;
  /** Axis/tooltip value formatter — defaults to 2 decimal places */
  valueFormat?: (v: number) => string;
}

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  payload?: FactorBeta;
}

function FactorTooltip({
  active,
  payload,
  valueFormat,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  valueFormat: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  const benchmarkLine =
    row.benchmark != null
      ? { label: 'Benchmark', value: valueFormat(row.benchmark) }
      : row.tStat != null
      ? { label: 't-stat', value: row.tStat.toFixed(2) }
      : undefined;

  return (
    <ChartTooltip
      title={row.tStat != null ? `${row.name} (t = ${row.tStat.toFixed(2)})` : row.name}
      value={`${row.beta >= 0 ? '+' : ''}${valueFormat(row.beta)}`}
      {...(benchmarkLine ? { benchmark: benchmarkLine } : {})}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Diverging horizontal bar chart for factor exposure / active tilts.
 * Bars grow left or right from a zero baseline; color encodes sign, and
 * (when a t-stat is supplied) desaturates rows below the |t| >= 2
 * significance threshold rather than pretending every exposure is real.
 */
export function FactorExposureChart({ factors, height, valueFormat }: FactorExposureChartProps) {
  const fmt = valueFormat ?? ((v: number) => v.toFixed(2));

  const rows = useMemo(
    () =>
      factors.map((f) => ({
        ...f,
        significant: f.significant ?? (f.tStat == null || Math.abs(f.tStat) >= 2),
      })),
    [factors],
  );

  const maxAbs = useMemo(
    () => Math.max(...rows.map((f) => Math.abs(f.beta)), 0.001),
    [rows],
  );

  const hasTStat = rows.some((f) => f.tStat != null);
  const chartHeight = height ?? Math.max(rows.length * 32 + 40, 140);

  const legendRowStyle: CSSProperties = {
    display: 'flex',
    gap: 'var(--space-4)',
    marginTop: 'var(--space-1)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
  };

  const legendItemStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  };

  const swatchStyle = (color: string): CSSProperties => ({
    width: 8,
    height: 8,
    borderRadius: 2,
    background: color,
  });

  return (
    <div className="animate-in" style={{ width: '100%' }}>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 32, bottom: 4, left: 4 }}
          barCategoryGap="28%"
        >
          <CartesianGrid
            strokeDasharray="none"
            stroke="var(--color-surface-border)"
            horizontal={false}
          />
          <XAxis
            type="number"
            domain={[-maxAbs * 1.15, maxAbs * 1.15]}
            tick={{ fill: 'var(--color-text-tertiary)', fontFamily: 'var(--font-data)', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={fmt}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fill: 'var(--color-text-primary)', fontFamily: 'var(--font-ui)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <ReferenceLine x={0} stroke="var(--color-surface-border-strong)" strokeWidth={1} />
          <Tooltip
            content={<FactorTooltip valueFormat={fmt} />}
            cursor={{ fill: 'var(--color-surface-raised)', opacity: 0.4 }}
          />
          <Bar dataKey="beta" radius={[2, 2, 2, 2]} maxBarSize={16} isAnimationActive={false}>
            {rows.map((f, i) => {
              const color = !f.significant
                ? 'var(--color-text-tertiary)'
                : f.beta >= 0
                ? 'var(--color-signal-positive)'
                : 'var(--color-signal-negative)';
              return <Cell key={i} fill={color} fillOpacity={f.significant ? 1 : 0.55} />;
            })}
            <LabelList
              dataKey="beta"
              position="right"
              formatter={(v: number | string | boolean | null | undefined) => {
                const n = typeof v === 'number' ? v : Number(v);
                return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${fmt(n)}` : '';
              }}
              style={{ fontFamily: 'var(--font-data)', fontSize: 10, fill: 'var(--color-text-secondary)' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div style={legendRowStyle}>
        <span style={legendItemStyle}>
          <span style={swatchStyle('var(--color-signal-positive)')} />
          Positive
        </span>
        <span style={legendItemStyle}>
          <span style={swatchStyle('var(--color-signal-negative)')} />
          Negative
        </span>
        {hasTStat && (
          <span style={legendItemStyle}>
            <span style={swatchStyle('var(--color-text-tertiary)')} />
            Not significant (|t| &lt; 2)
          </span>
        )}
      </div>
    </div>
  );
}

export default FactorExposureChart;
