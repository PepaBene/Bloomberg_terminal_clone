import { useState, useMemo, useRef, useCallback } from 'react';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface PeerPoint {
  name: string;
  ticker: string;
  x: number;
  y: number;
  marketCap: number;
}

export interface PeerScatterProps {
  peers: PeerPoint[];
  xLabel: string;
  yLabel: string;
  highlightTicker?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const MARGIN = { top: 16, right: 24, bottom: 40, left: 56 };
const MIN_DOT = 4;
const MAX_DOT = 20;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function PeerScatter({ peers, xLabel, yLabel, highlightTicker }: PeerScatterProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const height = 360;

  /* Observe container width */
  const containerRef = useRef<HTMLDivElement>(null);
  const roRef = useRef<ResizeObserver | null>(null);

  const setRef = useCallback((node: HTMLDivElement | null) => {
    if (roRef.current) roRef.current.disconnect();
    if (node) {
      containerRef.current = node;
      const ro = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (entry) setContainerWidth(entry.contentRect.width);
      });
      ro.observe(node);
      roRef.current = ro;
    }
  }, []);

  /* Tooltip state */
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    point: PeerPoint;
  } | null>(null);

  /* Scales */
  const { xScale, yScale, rScale, xTicks, yTicks } = useMemo(() => {
    const xVals = peers.map((p) => p.x);
    const yVals = peers.map((p) => p.y);
    const mcVals = peers.map((p) => p.marketCap);

    const xMin = Math.min(...xVals);
    const xMax = Math.max(...xVals);
    const yMin = Math.min(...yVals);
    const yMax = Math.max(...yVals);
    const mcMin = Math.min(...mcVals);
    const mcMax = Math.max(...mcVals);

    const plotW = containerWidth - MARGIN.left - MARGIN.right;
    const plotH = height - MARGIN.top - MARGIN.bottom;

    const xPad = (xMax - xMin) * 0.1 || 1;
    const yPad = (yMax - yMin) * 0.1 || 1;

    const xs = (v: number) =>
      MARGIN.left + ((v - (xMin - xPad)) / ((xMax + xPad) - (xMin - xPad))) * plotW;
    const ys = (v: number) =>
      MARGIN.top + plotH - ((v - (yMin - yPad)) / ((yMax + yPad) - (yMin - yPad))) * plotH;
    const rs = (mc: number) => {
      const range = mcMax - mcMin || 1;
      const t = (mc - mcMin) / range;
      return MIN_DOT + t * (MAX_DOT - MIN_DOT);
    };

    /* Generate ticks */
    const generateTicks = (min: number, max: number, count: number): number[] => {
      const step = (max - min) / (count - 1) || 1;
      return Array.from({ length: count }, (_, i) => min + step * i);
    };

    return {
      xScale: xs,
      yScale: ys,
      rScale: rs,
      xTicks: generateTicks(xMin, xMax, 5),
      yTicks: generateTicks(yMin, yMax, 5),
    };
  }, [peers, containerWidth, height]);

  const plotW = containerWidth - MARGIN.left - MARGIN.right;
  const plotH = height - MARGIN.top - MARGIN.bottom;

  return (
    <div ref={setRef} className="terminal-panel" style={{ width: '100%', position: 'relative' }}>
      {/* Header */}
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: 8,
        }}
      >
        Peer Comparison
      </div>

      <svg ref={svgRef} width={containerWidth} height={height} style={{ display: 'block' }}>
        {/* Grid lines */}
        {xTicks.map((t, i) => (
          <line
            key={`xg-${i}`}
            x1={xScale(t)}
            x2={xScale(t)}
            y1={MARGIN.top}
            y2={MARGIN.top + plotH}
            stroke={CHART_THEME.colors.grid}
            strokeDasharray="3 3"
          />
        ))}
        {yTicks.map((t, i) => (
          <line
            key={`yg-${i}`}
            x1={MARGIN.left}
            x2={MARGIN.left + plotW}
            y1={yScale(t)}
            y2={yScale(t)}
            stroke={CHART_THEME.colors.grid}
            strokeDasharray="3 3"
          />
        ))}

        {/* X axis labels */}
        {xTicks.map((t, i) => (
          <text
            key={`xl-${i}`}
            x={xScale(t)}
            y={MARGIN.top + plotH + 16}
            textAnchor="middle"
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
              fill: CHART_THEME.colors.axis,
            }}
          >
            {t.toFixed(1)}
          </text>
        ))}

        {/* Y axis labels */}
        {yTicks.map((t, i) => (
          <text
            key={`yl-${i}`}
            x={MARGIN.left - 8}
            y={yScale(t)}
            textAnchor="end"
            dominantBaseline="central"
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
              fill: CHART_THEME.colors.axis,
            }}
          >
            {t.toFixed(1)}
          </text>
        ))}

        {/* X axis label */}
        <text
          x={MARGIN.left + plotW / 2}
          y={height - 4}
          textAnchor="middle"
          style={{
            fontFamily: CHART_THEME.fonts.ui,
            fontSize: 11,
            fill: CHART_THEME.colors.textSecondary,
          }}
        >
          {xLabel}
        </text>

        {/* Y axis label */}
        <text
          x={12}
          y={MARGIN.top + plotH / 2}
          textAnchor="middle"
          transform={`rotate(-90, 12, ${MARGIN.top + plotH / 2})`}
          style={{
            fontFamily: CHART_THEME.fonts.ui,
            fontSize: 11,
            fill: CHART_THEME.colors.textSecondary,
          }}
        >
          {yLabel}
        </text>

        {/* Dots */}
        {peers.map((p) => {
          const isHighlighted = highlightTicker != null && p.ticker === highlightTicker;
          const cx = xScale(p.x);
          const cy = yScale(p.y);
          const r = rScale(p.marketCap);

          return (
            <g key={p.ticker}>
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={isHighlighted ? CHART_THEME.colors.accent : CHART_THEME.colors.series[0]}
                opacity={isHighlighted ? 1 : 0.6}
                stroke={isHighlighted ? CHART_THEME.colors.textPrimary : 'none'}
                strokeWidth={isHighlighted ? 1.5 : 0}
                style={{ cursor: 'pointer', transition: 'opacity 120ms ease' }}
                onMouseEnter={() => setTooltip({ x: cx, y: cy, point: p })}
                onMouseLeave={() => setTooltip(null)}
              />
              {/* Ticker label for highlighted */}
              {isHighlighted && (
                <text
                  x={cx}
                  y={cy - r - 4}
                  textAnchor="middle"
                  style={{
                    fontFamily: CHART_THEME.fonts.data,
                    fontSize: 10,
                    fontWeight: 600,
                    fill: CHART_THEME.colors.accent,
                    pointerEvents: 'none',
                  }}
                >
                  {p.ticker}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            top: tooltip.y - 12,
            transform: 'translate(-50%, -100%)',
            background: CHART_THEME.colors.tooltip.bg,
            border: `1px solid ${CHART_THEME.colors.surfaceBorderStrong}`,
            borderRadius: 4,
            padding: '8px 10px',
            boxShadow: CHART_THEME.shadowFloat,
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: 140,
          }}
        >
          <div
            style={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 11,
              color: CHART_THEME.colors.tooltip.label,
              marginBottom: 2,
            }}
          >
            {tooltip.point.name} ({tooltip.point.ticker})
          </div>
          <div
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 12,
              color: CHART_THEME.colors.tooltip.text,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {xLabel}: {tooltip.point.x.toFixed(2)}
          </div>
          <div
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 12,
              color: CHART_THEME.colors.tooltip.text,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {yLabel}: {tooltip.point.y.toFixed(2)}
          </div>
          <div
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 10,
              color: CHART_THEME.colors.tooltip.label,
              marginTop: 2,
            }}
          >
            Mkt Cap: ${(tooltip.point.marketCap / 1e9).toFixed(1)}B
          </div>
        </div>
      )}
    </div>
  );
}
