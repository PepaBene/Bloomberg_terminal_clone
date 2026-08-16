import { useMemo } from 'react';
import {
  ComposedChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { CHART_THEME } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface OrderBookLevel {
  price: number;
  size: number;
}

export interface OrderBookDepthChartProps {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  height?: number;
  priceFormat?: (v: number) => string;
}

interface DepthPoint {
  price: number;
  bidCum?: number;
  askCum?: number;
}

/* ------------------------------------------------------------------ */
/*  Cumulative depth series                                            */
/* ------------------------------------------------------------------ */

function buildDepth(bids: OrderBookLevel[], asks: OrderBookLevel[]): DepthPoint[] {
  // Bids walk away from the mid as price falls; asks walk away as price rises.
  const sortedBids = [...bids].sort((a, b) => b.price - a.price);
  const sortedAsks = [...asks].sort((a, b) => a.price - b.price);

  let cum = 0;
  const bidPoints: DepthPoint[] = sortedBids.map((b) => {
    cum += b.size;
    return { price: b.price, bidCum: cum };
  });

  cum = 0;
  const askPoints: DepthPoint[] = sortedAsks.map((a) => {
    cum += a.size;
    return { price: a.price, askCum: cum };
  });

  // Recombine and sort ascending by price for the chart's shared x-axis.
  return [...bidPoints, ...askPoints].sort((a, b) => a.price - b.price);
}

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

function DepthTooltip({
  active,
  payload,
  priceFormat,
}: {
  active?: boolean;
  payload?: Array<{ payload: DepthPoint }>;
  priceFormat: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  const isBid = row.bidCum != null;
  return (
    <ChartTooltip
      title={priceFormat(row.price)}
      value={(isBid ? row.bidCum! : row.askCum!).toLocaleString()}
      change={{ value: isBid ? 'Bid depth' : 'Ask depth', direction: isBid ? 'up' : 'down' }}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Classic order-book depth chart — cumulative bid size (green, step down
 * toward the mid) and cumulative ask size (red, step up away from the mid)
 * on a single shared price/size axis pair, converging at the spread.
 */
export function OrderBookDepthChart({ bids, asks, height = 220, priceFormat }: OrderBookDepthChartProps) {
  const fmt = priceFormat ?? ((v: number) => `$${v.toFixed(2)}`);
  const data = useMemo(() => buildDepth(bids, asks), [bids, asks]);

  const bestBid = useMemo(() => Math.max(...bids.map((b) => b.price), -Infinity), [bids]);
  const bestAsk = useMemo(() => Math.min(...asks.map((a) => a.price), Infinity), [asks]);
  const mid = Number.isFinite(bestBid) && Number.isFinite(bestAsk) ? (bestBid + bestAsk) / 2 : undefined;
  const spread = Number.isFinite(bestBid) && Number.isFinite(bestAsk) ? bestAsk - bestBid : undefined;

  return (
    <div className="animate-in" style={{ width: '100%' }}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={CHART_THEME.colors.grid} vertical={false} />
          <XAxis
            dataKey="price"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={fmt}
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART_THEME.colors.grid }}
          />
          <YAxis
            tick={{ fill: CHART_THEME.colors.axis, fontFamily: CHART_THEME.fonts.data, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          {mid != null && (
            <ReferenceLine
              x={mid}
              stroke={CHART_THEME.colors.surfaceBorderStrong}
              strokeWidth={1}
              label={{
                value: spread != null ? `Spread ${fmt(spread)}` : 'Mid',
                fill: CHART_THEME.colors.textSecondary,
                fontFamily: CHART_THEME.fonts.ui,
                fontSize: 9,
                position: 'insideTop',
              }}
            />
          )}
          <Tooltip content={<DepthTooltip priceFormat={fmt} />} cursor={{ stroke: CHART_THEME.colors.axis, strokeWidth: 1 }} />
          <Area
            type="stepAfter"
            dataKey="bidCum"
            stroke={CHART_THEME.colors.positive}
            fill={CHART_THEME.colors.positive}
            fillOpacity={0.15}
            strokeWidth={2}
            connectNulls={false}
            isAnimationActive={false}
            dot={false}
          />
          <Area
            type="stepBefore"
            dataKey="askCum"
            stroke={CHART_THEME.colors.negative}
            fill={CHART_THEME.colors.negative}
            fillOpacity={0.15}
            strokeWidth={2}
            connectNulls={false}
            isAnimationActive={false}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: 4, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: CHART_THEME.colors.positive }} />
          Bids
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: CHART_THEME.colors.negative }} />
          Asks
        </span>
      </div>
    </div>
  );
}

export default OrderBookDepthChart;
