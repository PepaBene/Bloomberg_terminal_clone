import { useMemo } from 'react';
import clsx from 'clsx';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  Cell,
  Tooltip as RechartsTooltip,
} from 'recharts';
import { CHART_THEME } from '../charts/chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface EarningsSurprise {
  quarter: string;
  actual: number;
  estimate: number;
  surprise_pct: number;
}

export interface EarningsSurpriseChartProps {
  surprises: EarningsSurprise[];
  /** Chart height in px (default 280) */
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function surpriseColor(pct: number): string {
  if (pct > 0) return CHART_THEME.colors.positive;
  if (pct < 0) return CHART_THEME.colors.negative;
  return CHART_THEME.colors.neutral;
}

interface StreakResult {
  type: 'beats' | 'misses' | 'mixed';
  count: number;
}

function computeStreak(surprises: EarningsSurprise[]): StreakResult {
  if (surprises.length === 0) return { type: 'mixed', count: 0 };

  const reversed = [...surprises].reverse();
  const first = reversed[0];
  if (!first) return { type: 'mixed', count: 0 };
  const direction = first.surprise_pct >= 0 ? 'beats' : 'misses';
  let count = 0;

  for (const s of reversed) {
    const isMatch = direction === 'beats' ? s.surprise_pct >= 0 : s.surprise_pct < 0;
    if (isMatch) {
      count++;
    } else {
      break;
    }
  }

  return { type: direction, count };
}

/* ------------------------------------------------------------------ */
/*  Custom tooltip (matches ChartTooltip pattern)                      */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  payload?: Record<string, unknown>;
}

function SurpriseTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload as EarningsSurprise | undefined;
  if (!d) return null;

  const color = surpriseColor(d.surprise_pct);

  return (
    <div
      style={{
        background: 'var(--surface-raised)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-2) var(--space-3)',
        boxShadow: 'var(--shadow-float)',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          marginBottom: 'var(--space-1)',
        }}
      >
        {d.quarter}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
        <TooltipRow label="Actual" value={`$${d.actual.toFixed(2)}`} color="var(--text-primary)" />
        <TooltipRow label="Estimate" value={`$${d.estimate.toFixed(2)}`} color="var(--text-secondary)" />
        <TooltipRow
          label="Surprise"
          value={`${d.surprise_pct >= 0 ? '+' : ''}${d.surprise_pct.toFixed(1)}%`}
          color={color}
        />
      </div>
    </div>
  );
}

function TooltipRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-4)', minWidth: 120 }}>
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function EarningsSurpriseChart({
  surprises,
  height = 280,
  className,
}: EarningsSurpriseChartProps) {
  const chartData = useMemo(
    () =>
      surprises.map((s) => ({
        ...s,
        diff: s.actual - s.estimate,
      })),
    [surprises],
  );

  const streak = useMemo(() => computeStreak(surprises), [surprises]);

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-3)',
      }}
    >
      {/* Header: title + streak counter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Earnings Surprises
        </span>
        {streak.count > 1 && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              fontVariantNumeric: 'tabular-nums',
              color: streak.type === 'beats'
                ? 'var(--accent-primary)'
                : 'var(--signal-negative)',
              padding: '2px var(--space-2)',
              background: streak.type === 'beats'
                ? 'color-mix(in srgb, var(--accent-primary) 15%, transparent)'
                : 'color-mix(in srgb, var(--signal-negative) 15%, transparent)',
              borderRadius: 'var(--radius-sm)',
              whiteSpace: 'nowrap',
            }}
          >
            {streak.count} consecutive {streak.type}
          </span>
        )}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={CHART_THEME.colors.grid}
            vertical={false}
          />
          <XAxis
            dataKey="quarter"
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.ui, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART_THEME.colors.grid }}
          />
          <YAxis
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `$${v.toFixed(2)}`}
          />
          <RechartsTooltip
            content={<SurpriseTooltip />}
            cursor={{ fill: CHART_THEME.colors.accentGlow }}
          />
          <ReferenceLine
            y={0}
            stroke={CHART_THEME.colors.surfaceBorderStrong}
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
          <Bar dataKey="diff" radius={[2, 2, 0, 0]} maxBarSize={32}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={surpriseColor(entry.surprise_pct)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
