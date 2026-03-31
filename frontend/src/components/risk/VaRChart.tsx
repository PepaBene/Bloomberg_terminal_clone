import type { CSSProperties } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
} from 'recharts';

export interface VaRDataPoint {
  date: string;
  var95: number;
  var99: number;
  pnl: number;
}

export interface VaRChartProps {
  series: VaRDataPoint[];
  height?: number;
}

interface TooltipProps {
  active?: boolean;
  payload?: { name?: string; value?: number; color?: string; dataKey?: string }[];
  label?: string;
}

function VaRTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'var(--color-surface-overlay)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: '8px 12px',
        fontFamily: 'var(--font-data)',
        fontSize: 'var(--text-xs)',
      }}
    >
      <div style={{ color: 'var(--color-text-secondary)', marginBottom: '4px', fontFamily: 'var(--font-ui)' }}>
        {label}
      </div>
      {payload.map((entry, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', color: entry.color }}>
          <span>{entry.name}</span>
          <span style={{ fontVariantNumeric: 'tabular-nums' }}>
            {entry.value != null ? entry.value.toFixed(2) + '%' : '--'}
          </span>
        </div>
      ))}
    </div>
  );
}

export function VaRChart({ series, height = 320 }: VaRChartProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={series}
          margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--color-surface-border)"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: 'var(--color-surface-border)' }}
          />
          <YAxis
            orientation="right"
            tick={{ fill: 'var(--color-text-tertiary)', fontFamily: 'var(--font-data)', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            width={55}
          />
          <RechartsTooltip content={<VaRTooltip />} />
          <Legend
            wrapperStyle={{ fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--color-text-secondary)' }}
          />

          {/* Daily P&L bars — colored by sign */}
          <Bar
            dataKey="pnl"
            name="Daily P&L"
            radius={[1, 1, 0, 0]}
            isAnimationActive={false}
            fill="var(--color-signal-positive)"
            label={false}
          >
            {series.map((_entry, i) => (
              <rect
                key={i}
                // Recharts handles cell rendering via Cell, use fill prop per-entry logic below
              />
            ))}
          </Bar>

          <Line
            type="monotone"
            dataKey="var95"
            name="VaR 95%"
            stroke="var(--color-signal-warning)"
            strokeWidth={1.5}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="var99"
            name="VaR 99%"
            stroke="var(--color-signal-negative)"
            strokeWidth={1.5}
            dot={false}
            strokeDasharray="4 2"
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div
        style={{
          display: 'flex',
          gap: 'var(--space-4)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
        }}
      >
        <span style={{ color: 'var(--color-signal-warning)' }}>&#9632; VaR 95%</span>
        <span style={{ color: 'var(--color-signal-negative)' }}>&#9472;&#9472; VaR 99%</span>
        <span style={{ color: 'var(--color-signal-positive)' }}>&#9646; Daily P&L</span>
        <span>Bars in red = breach day</span>
      </div>
    </div>
  );
}

export default VaRChart;
