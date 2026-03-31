import { useState, useRef, useCallback, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface RangeSelectorProps {
  /** Available range labels. Defaults to standard financial range set. */
  ranges?: string[];
  /** Currently active range label. */
  active: string;
  /** Fires when the user selects a different range. */
  onChange: (range: string) => void;
  /** Array of [timestamp, value] pairs to render as the mini-overview sparkline */
  overviewData?: Array<[number, number]>;
  /** Called when user drags a custom range on the overview bar */
  onCustomRange?: (startTs: number, endTs: number) => void;
  /** Currently selected time range as [startTs, endTs] */
  selectedRange?: [number, number];
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DEFAULT_RANGES = ['1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y', 'Max'] as const;

const OVERVIEW_HEIGHT = 32;

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const containerStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 0,
};

const buttonRowStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
  gap: 2,
};

const baseButtonStyle: CSSProperties = {
  height: 24,
  padding: '0 10px',
  border: 'none',
  borderRadius: 9999,
  cursor: 'pointer',
  fontFamily: CHART_THEME.fonts.ui,
  fontSize: 11,
  lineHeight: '24px',
  whiteSpace: 'nowrap',
  transition: 'background 120ms ease, color 120ms ease',
};

/* ------------------------------------------------------------------ */
/*  MiniOverview component                                             */
/* ------------------------------------------------------------------ */

interface MiniOverviewProps {
  data: Array<[number, number]>;
  onCustomRange?: (startTs: number, endTs: number) => void;
  selectedRange?: [number, number];
}

function MiniOverview({ data, onCustomRange, selectedRange }: MiniOverviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const overlayRef = useRef<SVGRectElement>(null);

  // Drag state stored in ref to avoid re-renders during drag
  const dragState = useRef<{
    dragging: boolean;
    startX: number;
    endX: number;
    containerLeft: number;
    containerWidth: number;
  }>({
    dragging: false,
    startX: 0,
    endX: 0,
    containerLeft: 0,
    containerWidth: 0,
  });

  // Force re-render only when drag starts/ends (not during)
  const [isDragging, setIsDragging] = useState(false);
  const [dragPixels, setDragPixels] = useState<{ start: number; end: number } | null>(null);

  // Compute data bounds (data.length > 0 is guaranteed by the caller)
  const tsMin = data[0]![0];
  const tsMax = data[data.length - 1]![0];
  const valMin = Math.min(...data.map(([, v]) => v));
  const valMax = Math.max(...data.map(([, v]) => v));
  const valRange = valMax - valMin || 1;

  // Build sparkline path (normalized to 100% width, OVERVIEW_HEIGHT px height)
  const buildPath = useCallback(
    (width: number): string => {
      if (data.length < 2) return '';
      const tsRange = tsMax - tsMin || 1;
      const points = data.map(([ts, val]) => {
        const x = ((ts - tsMin) / tsRange) * width;
        const y = OVERVIEW_HEIGHT - ((val - valMin) / valRange) * (OVERVIEW_HEIGHT - 4) - 2;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      });
      return `M ${points.join(' L ')}`;
    },
    [data, tsMin, tsMax, valMin, valRange],
  );

  // Convert pixel offset to timestamp
  const pixelToTs = useCallback(
    (px: number, containerWidth: number): number => {
      const clamped = Math.max(0, Math.min(containerWidth, px));
      return tsMin + (clamped / containerWidth) * (tsMax - tsMin);
    },
    [tsMin, tsMax],
  );

  // Convert timestamp to pixel offset
  const tsToPixel = useCallback(
    (ts: number, containerWidth: number): number => {
      return ((ts - tsMin) / (tsMax - tsMin || 1)) * containerWidth;
    },
    [tsMin, tsMax],
  );

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const startX = e.clientX - rect.left;
    dragState.current = {
      dragging: true,
      startX,
      endX: startX,
      containerLeft: rect.left,
      containerWidth: rect.width,
    };
    setIsDragging(true);
    setDragPixels({ start: startX, end: startX });
    e.preventDefault();
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!dragState.current.dragging) return;
    const endX = e.clientX - dragState.current.containerLeft;
    dragState.current.endX = endX;
    setDragPixels({
      start: dragState.current.startX,
      end: endX,
    });
  }, []);

  const handleMouseUp = useCallback(
    (e: MouseEvent) => {
      if (!dragState.current.dragging) return;
      const { startX, containerWidth } = dragState.current;
      const endX = e.clientX - dragState.current.containerLeft;
      dragState.current.dragging = false;
      setIsDragging(false);
      setDragPixels(null);

      if (Math.abs(endX - startX) > 4 && onCustomRange) {
        const rawStart = pixelToTs(Math.min(startX, endX), containerWidth);
        const rawEnd = pixelToTs(Math.max(startX, endX), containerWidth);
        onCustomRange(rawStart, rawEnd);
      }
    },
    [onCustomRange, pixelToTs],
  );

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
    return undefined;
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const overviewContainerStyle: CSSProperties = {
    height: OVERVIEW_HEIGHT,
    position: 'relative',
    marginTop: 'var(--space-2)',
    cursor: 'crosshair',
    userSelect: 'none',
    background: 'var(--color-surface-raised)',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--color-surface-border)',
    overflow: 'hidden',
  };

  // We need container width for path rendering; use a state-based width
  const [containerWidth, setContainerWidth] = useState(200);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 200;
      setContainerWidth(width);
    });
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const sparkPath = buildPath(containerWidth);

  // Selected range overlay pixels
  const selectedLeft =
    selectedRange != null ? tsToPixel(selectedRange[0], containerWidth) : null;
  const selectedRight =
    selectedRange != null ? tsToPixel(selectedRange[1], containerWidth) : null;

  // Drag overlay pixels
  const dragLeft = dragPixels != null ? Math.min(dragPixels.start, dragPixels.end) : null;
  const dragRight = dragPixels != null ? Math.max(dragPixels.start, dragPixels.end) : null;

  return (
    <div
      ref={containerRef}
      style={overviewContainerStyle}
      onMouseDown={handleMouseDown}
      role="presentation"
    >
      <svg
        ref={svgRef}
        width="100%"
        height={OVERVIEW_HEIGHT}
        style={{ display: 'block' }}
      >
        {/* Sparkline */}
        {sparkPath && (
          <path
            d={sparkPath}
            stroke="var(--color-text-tertiary)"
            strokeWidth={1}
            fill="none"
          />
        )}

        {/* Selected range overlay */}
        {selectedLeft != null && selectedRight != null && (
          <rect
            ref={overlayRef}
            x={selectedLeft}
            y={0}
            width={Math.max(0, selectedRight - selectedLeft)}
            height={OVERVIEW_HEIGHT}
            fill="color-mix(in srgb, var(--color-accent-primary) 15%, transparent)"
            stroke="var(--color-accent-primary)"
            strokeWidth={1}
          />
        )}

        {/* Drag selection overlay */}
        {dragLeft != null && dragRight != null && (
          <rect
            x={dragLeft}
            y={0}
            width={Math.max(0, dragRight - dragLeft)}
            height={OVERVIEW_HEIGHT}
            fill="color-mix(in srgb, var(--color-accent-primary) 15%, transparent)"
            stroke="var(--color-accent-primary)"
            strokeWidth={1}
          />
        )}
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RangeSelector({
  ranges = DEFAULT_RANGES as unknown as string[],
  active,
  onChange,
  overviewData,
  onCustomRange,
  selectedRange,
}: RangeSelectorProps) {
  const handleClick = useCallback(
    (range: string) => () => {
      if (range !== active) onChange(range);
    },
    [active, onChange],
  );

  const showOverview = overviewData != null && overviewData.length > 0;

  return (
    <div style={containerStyle} role="group" aria-label="Time range selector">
      <div style={buttonRowStyle}>
        {ranges.map((range) => {
          const isActive = range === active;
          return (
            <button
              key={range}
              type="button"
              onClick={handleClick(range)}
              aria-pressed={isActive}
              style={{
                ...baseButtonStyle,
                background: isActive
                  ? CHART_THEME.colors.accent
                  : CHART_THEME.colors.surfaceBorder,
                color: isActive
                  ? '#FFFFFF'
                  : CHART_THEME.colors.textSecondary,
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.color =
                    CHART_THEME.colors.textPrimary;
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.color =
                    CHART_THEME.colors.textSecondary;
                }
              }}
            >
              {range}
            </button>
          );
        })}
      </div>

      {showOverview && (
        <MiniOverview
          data={overviewData as Array<[number, number]>}
          onCustomRange={onCustomRange}
          selectedRange={selectedRange}
        />
      )}
    </div>
  );
}
