import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MonteCarloChartProps {
  /** Array of simulated outcome values */
  samples: number[];
  /** Number of histogram bins (default 50) */
  bins?: number;
  /** Current/base case value to mark with a vertical line */
  baseCase?: number;
  /** Confidence interval bounds to shade (e.g. [0.05, 0.95]) */
  confidenceInterval?: [number, number];
  height?: number;
  formatValue?: (v: number) => string;
  title?: string;
}

/* ------------------------------------------------------------------ */
/*  Internal bin shape                                                */
/* ------------------------------------------------------------------ */

interface HistBin {
  midpoint: number;
  count: number;
  inCI: boolean;
}

/* ------------------------------------------------------------------ */
/*  Percentile helper                                                 */
/* ------------------------------------------------------------------ */

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = p * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo] ?? 0;
  return (sorted[lo] ?? 0) + ((sorted[hi] ?? 0) - (sorted[lo] ?? 0)) * (idx - lo);
}

/* ------------------------------------------------------------------ */
/*  Histogram builder                                                 */
/* ------------------------------------------------------------------ */

function buildHistogram(
  samples: number[],
  numBins: number,
  ciLow: number | null,
  ciHigh: number | null,
): HistBin[] {
  if (samples.length === 0) return [];
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const range = max - min || 1;
  const binWidth = range / numBins;

  const counts = new Array<number>(numBins).fill(0);
  for (const v of samples) {
    const idx = Math.min(Math.floor((v - min) / binWidth), numBins - 1);
    counts[idx] = (counts[idx] ?? 0) + 1;
  }

  return counts.map((count, i) => {
    const midpoint = min + (i + 0.5) * binWidth;
    const inCI =
      ciLow !== null && ciHigh !== null
        ? midpoint >= ciLow && midpoint <= ciHigh
        : true;
    return { midpoint, count, inCI };
  });
}

/* ------------------------------------------------------------------ */
/*  Default formatter                                                 */
/* ------------------------------------------------------------------ */

const defaultFormat = (v: number): string => {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(1);
};

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                    */
/* ------------------------------------------------------------------ */

function MCTooltipContent({
  active,
  payload,
  formatValue = defaultFormat,
}: {
  active?: boolean;
  payload?: Array<{ payload: HistBin }>;
  formatValue?: (v: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const bin = payload[0]!.payload;
  if (!bin) return null;
  return (
    <ChartTooltip
      title={formatValue(bin.midpoint)}
      value={`${bin.count} samples`}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Stats row                                                         */
/* ------------------------------------------------------------------ */

interface StatItem {
  label: string;
  value: number;
}

function StatsRow({
  stats,
  formatValue,
}: {
  stats: StatItem[];
  formatValue: (v: number) => string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 'var(--space-3)',
        padding: 'var(--space-2) var(--space-3)',
        background: 'var(--color-surface-raised)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--color-surface-border)',
      }}
    >
      {stats.map((s) => (
        <div key={s.label} style={{ textAlign: 'center' }}>
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 10,
              color: 'var(--color-text-tertiary)',
              marginBottom: 2,
            }}
          >
            {s.label}
          </div>
          <div
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 11,
              color: 'var(--color-text-primary)',
              fontVariantNumeric: 'tabular-nums' as const,
            }}
          >
            {formatValue(s.value)}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  MonteCarloChart                                                   */
/* ------------------------------------------------------------------ */

const rootStyle: CSSProperties = { width: '100%' };

export function MonteCarloChart({
  samples,
  bins = 50,
  baseCase,
  confidenceInterval,
  height = 280,
  formatValue = defaultFormat,
  title,
}: MonteCarloChartProps) {
  const sorted = useMemo(() => [...samples].sort((a, b) => a - b), [samples]);

  const ciLow = useMemo(
    () => (confidenceInterval ? percentile(sorted, confidenceInterval[0]) : null),
    [sorted, confidenceInterval],
  );
  const ciHigh = useMemo(
    () => (confidenceInterval ? percentile(sorted, confidenceInterval[1]) : null),
    [sorted, confidenceInterval],
  );

  const histData = useMemo(
    () => buildHistogram(samples, bins, ciLow, ciHigh),
    [samples, bins, ciLow, ciHigh],
  );

  const mean = useMemo(
    () => (samples.length > 0 ? samples.reduce((a, b) => a + b, 0) / samples.length : 0),
    [samples],
  );

  const stats: StatItem[] = useMemo(
    () => [
      { label: 'P5', value: percentile(sorted, 0.05) },
      { label: 'P25', value: percentile(sorted, 0.25) },
      { label: 'P50', value: percentile(sorted, 0.5) },
      { label: 'P75', value: percentile(sorted, 0.75) },
      { label: 'P95', value: percentile(sorted, 0.95) },
    ],
    [sorted],
  );

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
        <BarChart
          data={histData}
          margin={{ top: 12, right: 12, bottom: 20, left: 0 }}
          barCategoryGap={0}
          barGap={0}
        >
          <defs>
            <linearGradient id="mcGradient" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.4} />
              <stop offset="50%" stopColor="var(--color-chart-1)" stopOpacity={0.9} />
              <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0.4} />
            </linearGradient>
          </defs>

          <XAxis
            dataKey="midpoint"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={formatValue}
            tick={{
              fontFamily: 'var(--font-data)',
              fontSize: 10,
              fill: 'var(--color-text-secondary)',
            }}
            axisLine={false}
            tickLine={false}
            tickCount={6}
          />
          <YAxis
            tick={{
              fontFamily: 'var(--font-ui)',
              fontSize: 10,
              fill: 'var(--color-text-tertiary)',
            }}
            axisLine={false}
            tickLine={false}
            width={0}
          />

          <Tooltip
            content={<MCTooltipContent formatValue={formatValue} />}
            cursor={{ fill: 'var(--color-surface-raised)', opacity: 0.3 }}
          />

          {/* Confidence interval lower bound */}
          {ciLow !== null && (
            <ReferenceLine
              x={ciLow}
              stroke="var(--color-signal-warning)"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              label={{
                value: `CI ${confidenceInterval ? (confidenceInterval[0] * 100).toFixed(0) : ''}%`,
                position: 'top',
                fontFamily: 'var(--font-ui)',
                fontSize: 9,
                fill: 'var(--color-signal-warning)',
              }}
            />
          )}

          {/* Confidence interval upper bound */}
          {ciHigh !== null && (
            <ReferenceLine
              x={ciHigh}
              stroke="var(--color-signal-warning)"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              label={{
                value: `CI ${confidenceInterval ? (confidenceInterval[1] * 100).toFixed(0) : ''}%`,
                position: 'top',
                fontFamily: 'var(--font-ui)',
                fontSize: 9,
                fill: 'var(--color-signal-warning)',
              }}
            />
          )}

          {/* Mean line */}
          <ReferenceLine
            x={mean}
            stroke="var(--color-text-tertiary)"
            strokeDasharray="3 3"
            strokeWidth={1.5}
            label={{
              value: 'Mean',
              position: 'top',
              fontFamily: 'var(--font-ui)',
              fontSize: 9,
              fill: 'var(--color-text-tertiary)',
            }}
          />

          {/* Base case line */}
          {baseCase !== undefined && (
            <ReferenceLine
              x={baseCase}
              stroke="var(--color-accent-primary)"
              strokeWidth={2}
              label={{
                value: 'Base',
                position: 'top',
                fontFamily: 'var(--font-ui)',
                fontSize: 9,
                fill: 'var(--color-accent-primary)',
              }}
            />
          )}

          <Bar dataKey="count" isAnimationActive={true} maxBarSize={32}>
            {histData.map((bin, i) => (
              <Cell
                key={`mc-cell-${i}`}
                fill={bin.inCI ? 'url(#mcGradient)' : 'var(--color-surface-raised)'}
                fillOpacity={bin.inCI ? 0.7 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stats summary */}
      {sorted.length > 0 && <StatsRow stats={stats} formatValue={formatValue} />}
    </div>
  );
}
