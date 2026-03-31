import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  LabelList,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface WaterfallBar {
  label: string;
  value: number;
  /** 'start' = absolute starting bar, 'end' = absolute ending bar, 'delta' = incremental change */
  type: 'start' | 'end' | 'delta';
  /** Optional annotation */
  note?: string;
}

export interface WaterfallChartProps {
  data: WaterfallBar[];
  height?: number;
  formatValue?: (v: number) => string;
  title?: string;
}

/* ------------------------------------------------------------------ */
/*  Internal row shape fed to recharts                                */
/* ------------------------------------------------------------------ */

interface WaterfallRow {
  label: string;
  base: number;    // transparent spacer
  bar: number;     // visible colored bar height (may be negative)
  value: number;   // raw value for labels / tooltip
  type: 'start' | 'end' | 'delta';
  note?: string;
  color: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const defaultFormat = (v: number): string => {
  const abs = Math.abs(v);
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(1);
};

function computeRows(data: WaterfallBar[]): WaterfallRow[] {
  let cursor = 0;
  return data.map((d) => {
    if (d.type === 'start') {
      const base = 0;
      const bar = d.value;
      cursor = d.value;
      return {
        label: d.label,
        base,
        bar,
        value: d.value,
        type: d.type,
        note: d.note,
        color: 'color-mix(in srgb, var(--color-accent-primary) 70%, var(--color-surface-base))',
      };
    }
    if (d.type === 'end') {
      const base = 0;
      const bar = cursor + d.value;
      return {
        label: d.label,
        base,
        bar,
        value: cursor + d.value,
        type: d.type,
        note: d.note,
        color: 'color-mix(in srgb, var(--color-accent-primary) 70%, var(--color-surface-base))',
      };
    }
    // delta
    const base = d.value >= 0 ? cursor : cursor + d.value;
    const bar = Math.abs(d.value);
    cursor += d.value;
    return {
      label: d.label,
      base,
      bar,
      value: d.value,
      type: d.type,
      note: d.note,
      color:
        d.value >= 0
          ? 'var(--color-signal-positive)'
          : 'var(--color-signal-negative)',
    };
  });
}

/* ------------------------------------------------------------------ */
/*  Custom label renderer                                             */
/* ------------------------------------------------------------------ */

interface LabelProps {
  x?: number;
  y?: number;
  width?: number;
  value?: number | string;
  index?: number;
  rows?: WaterfallRow[];
  formatValue?: (v: number) => string;
}

function ValueLabel({ x = 0, y = 0, width = 0, index = 0, rows = [], formatValue = defaultFormat }: LabelProps) {
  const row = rows[index];
  if (!row) return null;
  const displayVal = row.type === 'end' ? row.value : row.value;
  const prefix = row.type === 'delta' && row.value > 0 ? '+' : '';
  const label = `${prefix}${formatValue(displayVal)}`;
  const cx = x + width / 2;
  const cy = row.value >= 0 || row.type === 'end' || row.type === 'start' ? y - 4 : y + (row.bar || 0) + 12;
  return (
    <text
      x={cx}
      y={cy}
      textAnchor="middle"
      style={{
        fontFamily: 'var(--font-data)',
        fontSize: 11,
        fontVariantNumeric: 'tabular-nums' as const,
        fill: 'var(--color-text-secondary)',
        pointerEvents: 'none',
      }}
    >
      {label}
    </text>
  );
}

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

function WaterfallTooltipContent({
  active,
  payload,
  formatValue = defaultFormat,
}: {
  active?: boolean;
  payload?: Array<{ payload: WaterfallRow }>;
  formatValue?: (v: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]!.payload;
  if (!row) return null;
  const prefix = row.type === 'delta' && row.value > 0 ? '+' : '';
  const displayVal = row.type === 'end' ? row.value : row.value;
  return (
    <ChartTooltip
      title={row.label}
      value={`${prefix}${formatValue(displayVal)}`}
      {...(row.note ? { source: { label: row.note } } : {})}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  WaterfallChart                                                     */
/* ------------------------------------------------------------------ */

const rootStyle: CSSProperties = { width: '100%' };

export function WaterfallChart({
  data,
  height = 300,
  formatValue = defaultFormat,
  title,
}: WaterfallChartProps) {
  const rows = useMemo(() => computeRows(data), [data]);

  return (
    <div className="animate-in" style={rootStyle}>
      {title && (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: 'var(--space-2)',
          }}
        >
          {title}
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={rows}
          margin={{ top: 24, right: 16, bottom: 8, left: 0 }}
          barCategoryGap="20%"
        >
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{
              fontFamily: 'var(--font-ui)',
              fontSize: 11,
              fill: 'var(--color-text-secondary)',
            }}
          />
          <YAxis hide />
          <ReferenceLine y={0} stroke="var(--color-surface-border)" strokeWidth={1} />
          <Tooltip
            content={<WaterfallTooltipContent formatValue={formatValue} />}
            cursor={{ fill: 'var(--color-surface-raised)', opacity: 0.4 }}
          />

          {/* Transparent spacer bar — pushes visible bar up to correct cumulative level */}
          <Bar dataKey="base" stackId="wf" fill="transparent" isAnimationActive={false} />

          {/* Visible colored bar */}
          <Bar dataKey="bar" stackId="wf" isAnimationActive={true} radius={[2, 2, 0, 0]}>
            {rows.map((row, i) => (
              <Cell key={`cell-${i}`} fill={row.color} />
            ))}
            <LabelList
              content={(props) => (
                <ValueLabel
                  {...(props as LabelProps)}
                  rows={rows}
                  formatValue={formatValue}
                />
              )}
            />
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
