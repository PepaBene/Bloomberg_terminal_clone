import type { CSSProperties } from 'react';
import { DonutChart } from '@/components/charts/DonutChart';
import type { DonutDataPoint } from '@/components/charts/DonutChart';

export interface SectorWeight {
  name: string;
  weight: number;
  color?: string;
}

export interface SectorWeightsPieProps {
  sectors: SectorWeight[];
  height?: number;
}

const CHART_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-6)',
  'var(--color-chart-7)',
  'var(--color-chart-8)',
];

// DonutChart uses seriesColor internally, but we supply explicit colors via data
// We need to use resolved hex/rgb values since DonutChart passes them to SVG
// Instead we'll render the chart with explicit CSS var strings and a custom legend
export function SectorWeightsPie({ sectors, height = 300 }: SectorWeightsPieProps) {
  const total = sectors.reduce((s, sec) => s + sec.weight, 0) || 1;

  const data: DonutDataPoint[] = sectors.map((sec, i) => ({
    name: sec.name,
    value: sec.weight,
    color: sec.color ?? CHART_COLORS[i % CHART_COLORS.length],
  }));

  const containerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-4)',
  };

  const legendStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    minWidth: '160px',
    maxHeight: `${height}px`,
    overflowY: 'auto',
  };

  const legendItemStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={{ flex: '0 0 auto', width: `${height}px` }}>
        <DonutChart
          data={data}
          height={height}
          centerLabel="Sectors"
          centerValue={`${sectors.length}`}
        />
      </div>

      <div style={legendStyle}>
        {sectors.map((sec, i) => {
          const color = sec.color ?? CHART_COLORS[i % CHART_COLORS.length];
          const pct = ((sec.weight / total) * 100).toFixed(1);
          return (
            <div key={sec.name} style={legendItemStyle}>
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  borderRadius: '2px',
                  background: color,
                  flexShrink: 0,
                }}
              />
              <span style={{ flex: 1, color: 'var(--color-text-secondary)', minWidth: 0 }}>
                {sec.name}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                  color: 'var(--color-text-primary)',
                }}
              >
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default SectorWeightsPie;
