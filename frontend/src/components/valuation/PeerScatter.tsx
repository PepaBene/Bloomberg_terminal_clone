import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { LassoSelection, useLassoSelection } from '../charts/LassoSelection';
import type { LassoPoint } from '../charts/LassoSelection';

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
  onLassoSelect?: (selectedTickers: string[]) => void;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const MARGIN = { top: 16, right: 24, bottom: 40, left: 56 };
const MIN_DOT = 4;
const MAX_DOT = 20;

/* CSS variable values resolved at render-time via getComputedStyle
   would be ideal, but for SVG inline styles we use the token values
   directly from the design spec so they stay in sync with tokens.css. */
const C = {
  grid: 'var(--color-surface-border)',
  axis: 'var(--color-text-secondary)',
  axisLabel: 'var(--color-text-secondary)',
  dotDefault: 'var(--color-chart-1)',
  dotAccent: 'var(--color-accent-primary)',
  textPrimary: 'var(--color-text-primary)',
  textSecondary: 'var(--color-text-secondary)',
  textTertiary: 'var(--color-text-tertiary)',
  surfaceRaised: 'var(--color-surface-raised)',
  surfaceBorder: 'var(--color-surface-border)',
  surfaceBorderStrong: 'var(--color-surface-border-strong)',
} as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function PeerScatter({ peers, xLabel, yLabel, highlightTicker, onLassoSelect }: PeerScatterProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const height = 360;

  /* Lasso state */
  const [lassoActive, setLassoActive] = useState(false);
  const [lassoPolygon, setLassoPolygon] = useState<LassoPoint[] | null>(null);

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

  /* Hovered dot */
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);

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

  /* Map peers to lasso-testable points (SVG coordinate space) */
  const lassoPoints = useMemo(
    () =>
      peers.map((p) => ({
        id: p.ticker,
        x: xScale(p.x),
        y: yScale(p.y),
      })),
    [peers, xScale, yScale],
  );

  const selectedIds = useLassoSelection(lassoPoints, lassoPolygon);

  /* Notify parent when selection changes */
  useEffect(() => {
    onLassoSelect?.(selectedIds);
  }, [selectedIds, onLassoSelect]);

  return (
    <div ref={setRef} className="terminal-panel animate-in" style={{ width: '100%', position: 'relative' }}>
      {/* Header */}
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
        Peer Comparison
      </div>

      {/* Lasso toggle button */}
      <button
        onClick={() => {
          setLassoActive((v) => !v);
          if (lassoActive) {
            setLassoPolygon(null);
          }
        }}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          zIndex: 20,
          cursor: 'pointer',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          padding: '3px 8px',
          borderRadius: 'var(--radius-sm)',
          lineHeight: 1.5,
          ...(lassoActive
            ? {
                background: 'color-mix(in srgb, var(--color-accent-primary) 15%, transparent)',
                border: '1px solid var(--color-accent-primary)',
                color: 'var(--color-accent-primary)',
              }
            : {
                background: 'var(--color-surface-raised)',
                border: '1px solid var(--color-surface-border)',
                color: 'var(--color-text-tertiary)',
              }),
        }}
      >
        ⬡ Lasso
      </button>

      {/* Chart container — relative so the SVG overlay is positioned correctly */}
      <div style={{ position: 'relative' }}>
        <svg ref={svgRef} width={containerWidth} height={height} style={{ display: 'block' }}>
        {/* Grid lines */}
        {xTicks.map((t, i) => (
          <line
            key={`xg-${i}`}
            x1={xScale(t)}
            x2={xScale(t)}
            y1={MARGIN.top}
            y2={MARGIN.top + plotH}
            stroke={C.grid}
            strokeOpacity={0.3}
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
            stroke={C.grid}
            strokeOpacity={0.3}
            strokeDasharray="3 3"
          />
        ))}

        {/* X axis tick labels */}
        {xTicks.map((t, i) => (
          <text
            key={`xl-${i}`}
            x={xScale(t)}
            y={MARGIN.top + plotH + 16}
            textAnchor="middle"
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fill: C.axis,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {t.toFixed(1)}
          </text>
        ))}

        {/* Y axis tick labels */}
        {yTicks.map((t, i) => (
          <text
            key={`yl-${i}`}
            x={MARGIN.left - 8}
            y={yScale(t)}
            textAnchor="end"
            dominantBaseline="central"
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fill: C.axis,
              fontVariantNumeric: 'tabular-nums',
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
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fill: C.axisLabel,
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
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fill: C.axisLabel,
          }}
        >
          {yLabel}
        </text>

        {/* Glow filter for hover effect */}
        <defs>
          <filter id="peer-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="var(--color-accent-primary)" floodOpacity="0.5" />
          </filter>
        </defs>

        {/* Dots */}
        {peers.map((p) => {
          const isHighlighted = highlightTicker != null && p.ticker === highlightTicker;
          const isHovered = hoveredTicker === p.ticker;
          const isSelected = selectedIds.includes(p.ticker);
          const hasSelection = selectedIds.length > 0;
          const cx = xScale(p.x);
          const cy = yScale(p.y);
          const r = rScale(p.marketCap);

          return (
            <g key={p.ticker}>
              <circle
                cx={cx}
                cy={cy}
                r={isHovered ? r + 2 : r}
                fill={isHighlighted ? C.dotAccent : C.dotDefault}
                opacity={
                  hasSelection
                    ? isSelected
                      ? 1
                      : 0.2
                    : isHighlighted || isHovered
                      ? 1
                      : 0.6
                }
                stroke={isSelected ? C.dotAccent : isHighlighted ? C.textPrimary : 'none'}
                strokeWidth={isSelected || isHighlighted ? 1.5 : 0}
                filter={isHovered ? 'url(#peer-glow)' : undefined}
                style={{ cursor: 'pointer', transition: 'all 120ms ease' }}
                onMouseEnter={() => {
                  setHoveredTicker(p.ticker);
                  setTooltip({ x: cx, y: cy, point: p });
                }}
                onMouseLeave={() => {
                  setHoveredTicker(null);
                  setTooltip(null);
                }}
              />
              {/* Ticker label for highlighted or hovered */}
              {(isHighlighted || isHovered) && (
                <text
                  x={cx}
                  y={cy - r - 6}
                  textAnchor="middle"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    fill: isHighlighted ? C.dotAccent : C.textPrimary,
                    pointerEvents: 'none',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {p.ticker}
                </text>
              )}
            </g>
          );
        })}
        </svg>

        {/* Lasso overlay — sits on top of the SVG */}
        <LassoSelection
          active={lassoActive}
          width={containerWidth}
          height={height}
          onSelect={(poly) => {
            setLassoPolygon(poly);
            setLassoActive(false);
          }}
          onClear={() => setLassoPolygon(null)}
        />

        {/* Tooltip */}
        {tooltip && (
          <div
            style={{
              position: 'absolute',
              left: tooltip.x,
              top: tooltip.y - 12,
              transform: 'translate(-50%, -100%)',
              background: 'var(--color-surface-raised)',
              border: `1px solid var(--color-surface-border-strong)`,
              borderRadius: 'var(--radius-sm)',
              padding: 'var(--space-2) var(--space-3)',
              boxShadow: 'var(--shadow-float)',
              pointerEvents: 'none',
              zIndex: 10,
              minWidth: 140,
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-1)',
              }}
            >
              {tooltip.point.name} ({tooltip.point.ticker})
            </div>
            <div
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-base)',
                color: 'var(--color-text-primary)',
                fontVariantNumeric: 'tabular-nums' as const,
              }}
            >
              {xLabel}: {tooltip.point.x.toFixed(2)}
            </div>
            <div
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-base)',
                color: 'var(--color-text-primary)',
                fontVariantNumeric: 'tabular-nums' as const,
              }}
            >
              {yLabel}: {tooltip.point.y.toFixed(2)}
            </div>
            <div
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                marginTop: 'var(--space-1)',
                fontVariantNumeric: 'tabular-nums' as const,
              }}
            >
              Mkt Cap: ${(tooltip.point.marketCap / 1e9).toFixed(1)}B
            </div>
          </div>
        )}
      </div>

      {/* Selection badge */}
      {selectedIds.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            marginTop: 'var(--space-2)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-accent-primary)',
              background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-accent-primary) 30%, transparent)',
              borderRadius: 'var(--radius-sm)',
              padding: '2px 8px',
            }}
          >
            {selectedIds.length} {selectedIds.length === 1 ? 'company' : 'companies'} selected
          </span>
          <button
            onClick={() => {
              setLassoPolygon(null);
            }}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              background: 'var(--color-surface-raised)',
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '2px 8px',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}
