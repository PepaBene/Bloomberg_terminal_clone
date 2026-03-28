import { useState, useCallback } from 'react';
import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ChartEvent {
  date: string;
  label: string;
  type: 'earnings' | 'filing' | 'dividend' | 'split' | 'macro' | 'custom';
  color?: string;
}

export interface EventOverlayProps {
  events: ChartEvent[];
  chartWidth: number;
  chartHeight: number;
  /** Maps an ISO date string to an x pixel position within the chart area. */
  xScale: (date: string) => number;
  onEventClick?: (event: ChartEvent) => void;
}

/* ------------------------------------------------------------------ */
/*  Color mapping by event type (categorical palette from spec 5.1.3) */
/* ------------------------------------------------------------------ */

const EVENT_COLORS: Record<ChartEvent['type'], string> = {
  earnings: CHART_THEME.colors.highlight,    // amber — signal-highlight
  filing: CHART_THEME.colors.textSecondary,  // grey  — text-secondary
  dividend: CHART_THEME.colors.positive,     // green — signal-positive
  split: CHART_THEME.colors.accent,          // blue  — accent-primary
  macro: CHART_THEME.colors.neutral,         // slate — signal-neutral
  custom: CHART_THEME.colors.warning,        // orange — signal-warning
};

/* ------------------------------------------------------------------ */
/*  Tooltip                                                            */
/* ------------------------------------------------------------------ */

interface TooltipState {
  event: ChartEvent;
  x: number;
  y: number;
}

function EventTooltip({ event, x, y }: TooltipState) {
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y - 36,
        transform: 'translateX(-50%)',
        pointerEvents: 'none',
        background: CHART_THEME.colors.tooltip.bg,
        border: `1px solid ${CHART_THEME.colors.tooltip.border}`,
        borderRadius: 4,
        padding: '4px 8px',
        boxShadow: CHART_THEME.shadowFloat,
        whiteSpace: 'nowrap',
        zIndex: 20,
      }}
    >
      <div
        style={{
          fontFamily: CHART_THEME.fonts.ui,
          fontSize: 11,
          color: CHART_THEME.colors.tooltip.text,
          lineHeight: 1.4,
        }}
      >
        {event.label}
      </div>
      <div
        style={{
          fontFamily: CHART_THEME.fonts.data,
          fontSize: 10,
          color: CHART_THEME.colors.tooltip.label,
          marginTop: 1,
        }}
      >
        {event.date}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const MARKER_SIZE = 5;

export function EventOverlay({
  events,
  chartWidth,
  chartHeight,
  xScale,
  onEventClick,
}: EventOverlayProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const handleMouseEnter = useCallback(
    (event: ChartEvent, x: number) => () => {
      setTooltip({ event, x, y: chartHeight });
    },
    [chartHeight],
  );

  const handleMouseLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  const handleClick = useCallback(
    (event: ChartEvent) => () => {
      onEventClick?.(event);
    },
    [onEventClick],
  );

  return (
    <div
      style={{
        position: 'relative',
        width: chartWidth,
        height: 0,
        overflow: 'visible',
      }}
    >
      {/* Triangle markers rendered as an SVG overlay */}
      <svg
        width={chartWidth}
        height={chartHeight}
        style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', overflow: 'visible' }}
      >
        {events.map((ev) => {
          const x = xScale(ev.date);
          if (x < 0 || x > chartWidth) return null;

          const fill = ev.color ?? EVENT_COLORS[ev.type];
          const yBase = chartHeight;

          return (
            <polygon
              key={`${ev.type}-${ev.date}`}
              points={`${x},${yBase - MARKER_SIZE * 2} ${x - MARKER_SIZE},${yBase} ${x + MARKER_SIZE},${yBase}`}
              fill={fill}
              opacity={0.85}
              style={{ pointerEvents: 'auto', cursor: onEventClick ? 'pointer' : 'default' }}
              onMouseEnter={handleMouseEnter(ev, x)}
              onMouseLeave={handleMouseLeave}
              onClick={handleClick(ev)}
            />
          );
        })}
      </svg>

      {/* Tooltip layer */}
      {tooltip && <EventTooltip {...tooltip} />}
    </div>
  );
}
