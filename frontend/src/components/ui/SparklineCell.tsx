export interface SparklineCellProps {
  /** Array of numeric data points */
  data: number[];
  /** SVG width in px (default 60) */
  width?: number;
  /** SVG height in px (default 20) */
  height?: number;
  /** Force color direction: true = green, false = red. Auto-detects if omitted. */
  positive?: boolean;
}

/**
 * Tiny inline SVG sparkline for table cells.
 * Green if trending up (last > first), red if trending down.
 */
export function SparklineCell({
  data,
  width = 60,
  height = 20,
  positive,
}: SparklineCellProps) {
  if (data.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: 'inline-block', verticalAlign: 'middle' }}
      />
    );
  }

  const isPositive =
    positive !== undefined ? positive : data[data.length - 1]! > data[0]!;

  const color = isPositive
    ? 'var(--color-signal-positive)'
    : 'var(--color-signal-negative)';

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const padY = 2; // vertical padding inside SVG
  const usableHeight = height - padY * 2;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = padY + usableHeight - ((v - min) / range) * usableHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
