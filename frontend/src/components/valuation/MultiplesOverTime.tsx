import { useState, useCallback, useMemo } from 'react';
import {
  TimeSeriesChart,
  ComparisonLegend,
  seriesColor,
} from '@/components/charts';
import type { TimeSeriesSeries, ComparisonSeries } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MultiplesDataPoint {
  date: string;
  pe: number;
  evEbitda: number;
  ps: number;
  pbv: number;
}

export interface PeerMedians {
  pe: number;
  evEbitda: number;
}

export interface MultiplesOverTimeProps {
  data: MultiplesDataPoint[];
  peerMedians?: PeerMedians;
}

/* ------------------------------------------------------------------ */
/*  Series definitions                                                 */
/* ------------------------------------------------------------------ */

const SERIES_DEFS: { key: keyof Omit<MultiplesDataPoint, 'date'>; name: string; idx: number }[] = [
  { key: 'pe', name: 'P/E', idx: 0 },
  { key: 'evEbitda', name: 'EV/EBITDA', idx: 1 },
  { key: 'ps', name: 'P/S', idx: 2 },
  { key: 'pbv', name: 'P/BV', idx: 3 },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function MultiplesOverTime({ data, peerMedians }: MultiplesOverTimeProps) {
  /* Visibility state for each series */
  const [visible, setVisible] = useState<Record<string, boolean>>({
    pe: true,
    evEbitda: true,
    ps: true,
    pbv: true,
  });

  const handleToggle = useCallback((key: string) => {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  /* ComparisonLegend series */
  const legendSeries: ComparisonSeries[] = SERIES_DEFS.map((s) => ({
    key: s.key,
    name: s.name,
    color: seriesColor(s.idx),
    visible: visible[s.key] ?? true,
  }));

  /* Filtered TimeSeriesChart series */
  const chartSeries: TimeSeriesSeries[] = useMemo(
    () =>
      SERIES_DEFS
        .filter((s) => visible[s.key])
        .map((s) => ({
          key: s.key,
          name: s.name,
          color: seriesColor(s.idx),
          type: 'line' as const,
        })),
    [visible],
  );

  /* Recharts-compatible data (just pass through; keys match) */
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: d.date,
        value: d.pe,
        pe: d.pe,
        evEbitda: d.evEbitda,
        ps: d.ps,
        pbv: d.pbv,
      })),
    [data],
  );

  return (
    <div className="terminal-panel flex flex-col gap-3">
      {/* Header */}
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Valuation Multiples
      </div>

      {/* Legend */}
      <ComparisonLegend series={legendSeries} onToggle={handleToggle} />

      {/* Chart */}
      <TimeSeriesChart
        data={chartData}
        series={chartSeries}
        height={320}
        showTooltip
        showGrid
        yAxisFormat={(v) => v.toFixed(1) + 'x'}
        benchmarkLine={
          peerMedians && visible['pe']
            ? { value: peerMedians.pe, label: 'Peer P/E Median', color: 'var(--color-signal-neutral)' }
            : undefined
        }
      />

      {/* Peer median note */}
      {peerMedians && (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          Peer median P/E: {peerMedians.pe.toFixed(1)}x | EV/EBITDA: {peerMedians.evEbitda.toFixed(1)}x
        </div>
      )}
    </div>
  );
}
