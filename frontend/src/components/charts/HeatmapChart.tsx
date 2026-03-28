import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import * as d3 from 'd3';
import { CHART_THEME } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface HeatmapDataPoint {
  row: string;
  col: string;
  value: number;
}

export interface HeatmapChartProps {
  data: HeatmapDataPoint[];
  rows: string[];
  cols: string[];
  height?: number;
  colorScale?: 'diverging' | 'sequential';
  valueFormat?: (v: number) => string;
  onCellClick?: (row: string, col: string, value: number) => void;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const LABEL_WIDTH = 72;
const LABEL_HEIGHT = 24;
const CELL_PAD = 1;
const MIN_CELL = 24;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function HeatmapChart({
  data,
  rows,
  cols,
  height: heightProp,
  colorScale = 'diverging',
  valueFormat,
  onCellClick,
}: HeatmapChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);

  /* Observe container width */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setContainerWidth(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* Build a lookup map */
  const valueMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of data) {
      m.set(`${d.row}__${d.col}`, d.value);
    }
    return m;
  }, [data]);

  /* Color scale */
  const colorFn = useMemo(() => {
    const values = data.map((d) => d.value);
    const minV = Math.min(...values, 0);
    const maxV = Math.max(...values, 0);

    if (colorScale === 'diverging') {
      const extent = Math.max(Math.abs(minV), Math.abs(maxV)) || 1;
      return d3
        .scaleLinear<string>()
        .domain([-extent, 0, extent])
        .range([CHART_THEME.colors.negative, CHART_THEME.colors.surfaceBase, CHART_THEME.colors.positive])
        .clamp(true);
    }

    return d3
      .scaleLinear<string>()
      .domain([minV, maxV || 1])
      .range([CHART_THEME.colors.surfaceBase, CHART_THEME.colors.accent])
      .clamp(true);
  }, [data, colorScale]);

  /* Dimensions */
  const chartWidth = containerWidth;
  const cellW = Math.max(MIN_CELL, (chartWidth - LABEL_WIDTH) / cols.length - CELL_PAD);
  const cellH = Math.max(MIN_CELL, 28);
  const height = heightProp ?? rows.length * (cellH + CELL_PAD) + LABEL_HEIGHT + 8;

  /* Tooltip state */
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    row: string;
    col: string;
    value: number;
  } | null>(null);

  const [hovered, setHovered] = useState<string | null>(null);

  const fmt = valueFormat ?? ((v: number) => v.toFixed(2));

  const handleMouseEnter = useCallback(
    (row: string, col: string, value: number, x: number, y: number) => {
      setTooltip({ x, y, row, col, value });
      setHovered(`${row}__${col}`);
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    setTooltip(null);
    setHovered(null);
  }, []);

  const handleClick = useCallback(
    (row: string, col: string, value: number) => {
      onCellClick?.(row, col, value);
    },
    [onCellClick],
  );

  return (
    <div ref={containerRef} style={{ width: '100%', position: 'relative' }}>
      <svg
        width={chartWidth}
        height={height}
        style={{ display: 'block', overflow: 'visible' }}
      >
        {/* Column headers */}
        {cols.map((c, ci) => (
          <text
            key={`col-${c}`}
            x={LABEL_WIDTH + ci * (cellW + CELL_PAD) + cellW / 2}
            y={LABEL_HEIGHT - 6}
            textAnchor="middle"
            style={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
              fill: CHART_THEME.colors.textSecondary,
            }}
          >
            {c}
          </text>
        ))}

        {/* Rows */}
        {rows.map((r, ri) => {
          const ry = LABEL_HEIGHT + ri * (cellH + CELL_PAD);
          return (
            <g key={`row-${r}`}>
              {/* Row label */}
              <text
                x={LABEL_WIDTH - 8}
                y={ry + cellH / 2}
                textAnchor="end"
                dominantBaseline="central"
                style={{
                  fontFamily: CHART_THEME.fonts.ui,
                  fontSize: 10,
                  fill: CHART_THEME.colors.textSecondary,
                }}
              >
                {r}
              </text>

              {/* Cells */}
              {cols.map((c, ci) => {
                const key = `${r}__${c}`;
                const val = valueMap.get(key) ?? 0;
                const cx = LABEL_WIDTH + ci * (cellW + CELL_PAD);
                const isHov = hovered === key;

                return (
                  <g
                    key={key}
                    onMouseEnter={() => handleMouseEnter(r, c, val, cx + cellW / 2, ry + cellH / 2)}
                    onMouseLeave={handleMouseLeave}
                    onClick={() => handleClick(r, c, val)}
                    style={{ cursor: onCellClick ? 'pointer' : 'default' }}
                  >
                    <rect
                      x={cx}
                      y={ry}
                      width={cellW}
                      height={cellH}
                      rx={2}
                      fill={colorFn(val)}
                      stroke={isHov ? CHART_THEME.colors.accent : 'transparent'}
                      strokeWidth={isHov ? 1.5 : 0}
                    />
                    {/* Cell value text — only if cell is wide enough */}
                    {cellW > 36 && (
                      <text
                        x={cx + cellW / 2}
                        y={ry + cellH / 2}
                        textAnchor="middle"
                        dominantBaseline="central"
                        style={{
                          fontFamily: CHART_THEME.fonts.data,
                          fontSize: 9,
                          fill: CHART_THEME.colors.textPrimary,
                          pointerEvents: 'none',
                        }}
                      >
                        {fmt(val)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      {/* Floating tooltip using ChartTooltip */}
      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            top: tooltip.y - 54,
            transform: 'translateX(-50%)',
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <ChartTooltip
            title={`${tooltip.row} / ${tooltip.col}`}
            value={fmt(tooltip.value)}
          />
        </div>
      )}
    </div>
  );
}
