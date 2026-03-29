import { useMemo, useState } from 'react';
import { TimeSeriesChart } from '@/components/charts';
import type { TimeSeriesSeries } from '@/components/charts';
import { seriesColor } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SpreadDataPoint {
  date: string;
  oas: number;
  zSpread?: number;
  gSpread?: number;
}

export interface SpreadHistoryChartProps {
  data: SpreadDataPoint[];
  benchmarkSpread?: number;
  height?: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const ALL_SERIES: { key: keyof SpreadDataPoint; name: string }[] = [
  { key: 'oas', name: 'OAS' },
  { key: 'zSpread', name: 'Z-Spread' },
  { key: 'gSpread', name: 'G-Spread' },
];

export function SpreadHistoryChart({
  data,
  benchmarkSpread,
  height = 320,
  className,
}: SpreadHistoryChartProps) {
  const [visible, setVisible] = useState<Set<string>>(
    () => new Set(['oas']),
  );

  /** Only include series that have data */
  const availableSeries = useMemo(
    () =>
      ALL_SERIES.filter((s) =>
        data.some(
          (d) => d[s.key] != null && d[s.key] !== undefined,
        ),
      ),
    [data],
  );

  /** Active series definitions */
  const activeSeries = useMemo<TimeSeriesSeries[]>(
    () =>
      availableSeries
        .filter((s) => visible.has(s.key))
        .map((s, i) => ({
          key: s.key,
          name: s.name,
          color: seriesColor(i),
          type: 'area' as const,
        })),
    [availableSeries, visible],
  );

  const toggle = (key: string) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const benchmark = benchmarkSpread != null
    ? { value: benchmarkSpread, label: 'Benchmark', color: undefined }
    : undefined;

  return (
    <div className={className}>
      {/* Toggle pills */}
      <div
        className="flex items-center gap-2"
        style={{ marginBottom: '8px' }}
      >
        {availableSeries.map((s, i) => {
          const isActive = visible.has(s.key);
          const color = seriesColor(i);
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => toggle(s.key)}
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                padding: '2px 10px',
                borderRadius: '9999px',
                border: `1px solid ${isActive ? color : 'var(--color-surface-border)'}`,
                background: isActive ? `${color}22` : 'transparent',
                color: isActive ? color : 'var(--color-text-tertiary)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {s.name}
            </button>
          );
        })}
      </div>

      <TimeSeriesChart
        data={data.map((d) => ({ ...d, date: d.date, value: d.oas } as { date: string; value: number; [key: string]: unknown }))}
        series={activeSeries}
        height={height}
        showGrid
        showTooltip
        showLegend={false}
        yAxisFormat={(v) => `${v.toFixed(0)}bp`}
        benchmarkLine={benchmark}
      />
    </div>
  );
}
