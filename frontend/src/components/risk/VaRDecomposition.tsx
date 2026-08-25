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
} from 'recharts';
import { ChartTooltip } from '../charts/ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface VaRComponent {
  name: string;
  marginalVar: number;
  componentVar: number;
  percentContrib: number;
}

export interface VaRDecompositionProps {
  components: VaRComponent[];
  height?: number;
}

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

function DecompTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: VaRComponent }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  return (
    <ChartTooltip
      title={row.name}
      value={`${row.percentContrib.toFixed(1)}%`}
      series={[
        { name: 'Component VaR', value: `${row.componentVar.toFixed(2)}%`, color: 'var(--color-accent-primary)' },
        { name: 'Marginal VaR', value: `${row.marginalVar.toFixed(2)}%`, color: 'var(--color-text-secondary)' },
      ]}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Ranked horizontal bar chart of each position/asset's share of total
 * portfolio VaR. Severity-thresholded color (>20% critical, >10% warning)
 * since this is a risk-concentration reading, not series identity.
 */
export function VaRDecomposition({ components, height }: VaRDecompositionProps) {
  const sorted = useMemo(
    () => [...components].sort((a, b) => b.percentContrib - a.percentContrib),
    [components],
  );

  const total = useMemo(
    () => sorted.reduce((s, c) => s + c.componentVar, 0),
    [sorted],
  );

  const chartHeight = height ?? Math.max(sorted.length * 28 + 32, 140);

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 'var(--space-2)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
  };

  return (
    <div className="animate-in" style={{ width: '100%' }}>
      <div style={headerStyle}>
        <span>Contribution to Total VaR</span>
        <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)' }}>
          Total: {total.toFixed(2)}%
        </span>
      </div>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={sorted}
          layout="vertical"
          margin={{ top: 4, right: 40, bottom: 4, left: 4 }}
          barCategoryGap="24%"
        >
          <CartesianGrid strokeDasharray="none" stroke="var(--color-surface-border)" horizontal={false} />
          <XAxis
            type="number"
            unit="%"
            tick={{ fill: 'var(--color-text-tertiary)', fontFamily: 'var(--font-data)', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fill: 'var(--color-text-primary)', fontFamily: 'var(--font-ui)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<DecompTooltip />} cursor={{ fill: 'var(--color-surface-raised)', opacity: 0.4 }} />
          <Bar dataKey="percentContrib" radius={[0, 2, 2, 0]} maxBarSize={16} isAnimationActive={false}>
            {sorted.map((c, i) => {
              const color =
                c.percentContrib > 20
                  ? 'var(--color-signal-negative)'
                  : c.percentContrib > 10
                  ? 'var(--color-signal-warning)'
                  : 'var(--color-signal-neutral)';
              return <Cell key={i} fill={color} />;
            })}
            <LabelList
              dataKey="percentContrib"
              position="right"
              formatter={(v: number | string | boolean | null | undefined) => {
                const n = typeof v === 'number' ? v : Number(v);
                return Number.isFinite(n) ? `${n.toFixed(1)}%` : '';
              }}
              style={{ fontFamily: 'var(--font-data)', fontSize: 10, fill: 'var(--color-text-secondary)' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default VaRDecomposition;
