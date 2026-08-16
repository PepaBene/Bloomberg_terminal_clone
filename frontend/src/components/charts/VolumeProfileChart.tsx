import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { CHART_THEME } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface VolumeProfileLevel {
  price: number;
  volume: number;
}

export interface VolumeProfileChartProps {
  levels: VolumeProfileLevel[];
  height?: number;
  currentPrice?: number;
  priceFormat?: (v: number) => string;
}

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

function ProfileTooltip({
  active,
  payload,
  priceFormat,
  pocPrice,
}: {
  active?: boolean;
  payload?: Array<{ payload: VolumeProfileLevel }>;
  priceFormat: (v: number) => string;
  pocPrice?: number;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <ChartTooltip
      title={priceFormat(row.price)}
      value={row.volume.toLocaleString()}
      {...(row.price === pocPrice ? { change: { value: 'Point of control', direction: 'flat' as const } } : {})}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Horizontal volume-by-price histogram. The point of control (the price
 * level with the most traded volume) is the story here, so it carries the
 * accent color while every other level recedes to a muted gray — emphasis,
 * not a full categorical palette, since only one bar is the point.
 */
export function VolumeProfileChart({ levels, height, currentPrice, priceFormat }: VolumeProfileChartProps) {
  const fmt = priceFormat ?? ((v: number) => `$${v.toFixed(2)}`);

  const sorted = useMemo(() => [...levels].sort((a, b) => b.price - a.price), [levels]);
  const pocPrice = useMemo(
    () => sorted.reduce((best, l) => (l.volume > (best?.volume ?? -Infinity) ? l : best), sorted[0])?.price,
    [sorted],
  );

  const chartHeight = height ?? Math.max(sorted.length * 14 + 24, 160);

  return (
    <div className="animate-in" style={{ width: '100%' }}>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barCategoryGap="10%">
          <CartesianGrid stroke={CHART_THEME.colors.grid} horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          <YAxis
            type="category"
            dataKey="price"
            width={64}
            tickFormatter={fmt}
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          {currentPrice != null && (
            <ReferenceLine
              y={currentPrice}
              stroke={CHART_THEME.colors.accent}
              strokeWidth={1.5}
              label={{
                value: `Last ${fmt(currentPrice)}`,
                fill: CHART_THEME.colors.accent,
                fontFamily: CHART_THEME.fonts.ui,
                fontSize: 9,
                position: 'insideTopRight',
              }}
            />
          )}
          <Tooltip content={<ProfileTooltip priceFormat={fmt} pocPrice={pocPrice} />} cursor={{ fill: CHART_THEME.colors.accentGlow }} />
          <Bar dataKey="volume" radius={[0, 2, 2, 0]} maxBarSize={12} isAnimationActive={false}>
            {sorted.map((l, i) => (
              <Cell key={i} fill={l.price === pocPrice ? CHART_THEME.colors.accent : CHART_THEME.colors.textTertiary} fillOpacity={l.price === pocPrice ? 1 : 0.5} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: 4, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: CHART_THEME.colors.accent }} />
          Point of control
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: CHART_THEME.colors.textTertiary, opacity: 0.5 }} />
          Other levels
        </span>
      </div>
    </div>
  );
}

export default VolumeProfileChart;
