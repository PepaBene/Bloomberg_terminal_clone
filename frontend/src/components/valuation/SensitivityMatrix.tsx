import { useMemo } from 'react';
import { HeatmapChart } from '@/components/charts';
import type { HeatmapDataPoint } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SensitivityMatrixProps {
  waccValues: number[];
  growthValues: number[];
  priceMatrix: (number | null)[][];
  currentPrice?: number;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function SensitivityMatrix({
  waccValues,
  growthValues,
  priceMatrix,
  currentPrice,
}: SensitivityMatrixProps) {
  /* Build HeatmapChart data points */
  const { data, rows, cols } = useMemo(() => {
    const points: HeatmapDataPoint[] = [];
    const rowLabels = waccValues.map((w) => `${(w * 100).toFixed(1)}%`);
    const colLabels = growthValues.map((g) => `${(g * 100).toFixed(1)}%`);

    for (let ri = 0; ri < waccValues.length; ri++) {
      for (let ci = 0; ci < growthValues.length; ci++) {
        const price = priceMatrix[ri]?.[ci] ?? 0;
        /* Center the diverging scale on currentPrice so
           above = positive (green), below = negative (red) */
        const centeredValue = currentPrice != null ? price - currentPrice : price;
        points.push({
          row: rowLabels[ri] ?? '',
          col: colLabels[ci] ?? '',
          value: centeredValue,
        });
      }
    }

    return { data: points, rows: rowLabels, cols: colLabels };
  }, [waccValues, growthValues, priceMatrix, currentPrice]);

  const valueFormat = (v: number) => {
    const actual = currentPrice != null ? v + currentPrice : v;
    return `$${actual.toFixed(0)}`;
  };

  return (
    <div className="terminal-panel animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Sensitivity Analysis
        </span>
        {currentPrice != null && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            Current: ${currentPrice.toFixed(2)}
          </span>
        )}
      </div>

      {/* Axis labels */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          WACC {'\u2193'}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          Terminal Growth {'\u2192'}
        </span>
      </div>

      {/* Heatmap */}
      <HeatmapChart
        data={data}
        rows={rows}
        cols={cols}
        colorScale="diverging"
        valueFormat={valueFormat}
      />
    </div>
  );
}
