import { useMemo } from 'react';
import clsx from 'clsx';

export interface MiniChartProps {
  /** Data points to render */
  data: number[];
  /** SVG width in pixels (default: 80) */
  width?: number;
  /** SVG height in pixels (default: 24) */
  height?: number;
  /** Whether the trend is positive (green) or negative (red). Auto-detected if omitted. */
  positive?: boolean;
  /** Show an area fill at 15% opacity */
  fill?: boolean;
  /** Additional CSS class */
  className?: string;
}

export function MiniChart({
  data,
  width = 80,
  height = 24,
  positive,
  fill = true,
  className,
}: MiniChartProps) {
  const { polyline, polygon, isPositive } = useMemo(() => {
    if (data.length < 2) return { polyline: '', polygon: '', isPositive: true };

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Inset by 1px to avoid clipping
    const padX = 1;
    const padY = 2;
    const drawW = width - padX * 2;
    const drawH = height - padY * 2;

    const points = data.map((v, i) => {
      const x = padX + (i / (data.length - 1)) * drawW;
      const y = padY + drawH - ((v - min) / range) * drawH;
      return `${x},${y}`;
    });

    const line = points.join(' ');

    // Closed polygon for area fill
    const lastX = padX + drawW;
    const firstX = padX;
    const bottom = height;
    const area = `${line} ${lastX},${bottom} ${firstX},${bottom}`;

    // Auto-detect direction from first to last point
    const autoPositive =
      data.length >= 2 ? data[data.length - 1]! >= data[0]! : true;

    return {
      polyline: line,
      polygon: area,
      isPositive: positive ?? autoPositive,
    };
  }, [data, width, height, positive]);

  if (data.length < 2) return null;

  const strokeColor = isPositive
    ? 'var(--color-signal-positive)'
    : 'var(--color-signal-negative)';

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={clsx('block', className)}
      style={{ overflow: 'visible' }}
    >
      {fill && (
        <polygon
          points={polygon}
          fill={strokeColor}
          opacity={0.15}
        />
      )}
      <polyline
        points={polyline}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
