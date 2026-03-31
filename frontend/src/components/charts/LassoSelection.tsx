import { useState, useRef, useMemo, useCallback } from 'react';
import type { CSSProperties } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface LassoPoint {
  x: number;
  y: number;
}

export interface LassoSelectionProps {
  /** Container width/height — the SVG overlay covers this area */
  width: number;
  height: number;
  /** Called when lasso is completed with the polygon path */
  onSelect: (polygon: LassoPoint[]) => void;
  /** Called when selection is cleared */
  onClear: () => void;
  /** Whether lasso mode is active (default false) */
  active: boolean;
}

/* ------------------------------------------------------------------ */
/*  Point-in-polygon — ray casting algorithm                          */
/* ------------------------------------------------------------------ */

function pointInPolygon(px: number, py: number, polygon: LassoPoint[]): boolean {
  const n = polygon.length;
  if (n < 3) return false;
  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygon[i]!.x;
    const yi = polygon[i]!.y;
    const xj = polygon[j]!.x;
    const yj = polygon[j]!.y;
    const intersect =
      yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/* ------------------------------------------------------------------ */
/*  LassoSelection component                                          */
/* ------------------------------------------------------------------ */

const svgStyle: CSSProperties = {
  position: 'absolute',
  inset: 0,
  zIndex: 10,
};

export function LassoSelection({
  width,
  height,
  onSelect,
  onClear: _onClear,
  active,
}: LassoSelectionProps) {
  const [points, setPoints] = useState<LassoPoint[]>([]);
  const isDrawingRef = useRef(false);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!active) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      isDrawingRef.current = true;
      setPoints([{ x, y }]);
    },
    [active],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!active || !isDrawingRef.current) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setPoints((prev) => [...prev, { x, y }]);
    },
    [active],
  );

  const handleMouseUp = useCallback(() => {
    if (!active || !isDrawingRef.current) return;
    isDrawingRef.current = false;
    setPoints((prev) => {
      if (prev.length >= 3) {
        onSelect(prev);
      }
      return [];
    });
  }, [active, onSelect]);

  if (!active) return null;

  const pointsAttr = points.map((p) => `${p.x},${p.y}`).join(' ');
  const closingLine =
    points.length >= 2
      ? `${points.at(-1)!.x},${points.at(-1)!.y} ${points[0]!.x},${points[0]!.y}`
      : null;

  return (
    <svg
      width={width}
      height={height}
      style={{ ...svgStyle, cursor: 'crosshair', pointerEvents: 'all' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {points.length >= 2 && (
        <>
          {/* Filled polygon area */}
          <polygon
            points={pointsAttr}
            fill="var(--color-accent-primary)"
            fillOpacity={0.08}
            stroke="none"
          />
          {/* Dashed stroke outline */}
          <polyline
            points={pointsAttr}
            fill="none"
            stroke="var(--color-accent-primary)"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            strokeLinejoin="round"
          />
          {/* Closing line from last point back to first */}
          {closingLine && (
            <polyline
              points={closingLine}
              fill="none"
              stroke="var(--color-accent-primary)"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              strokeOpacity={0.5}
            />
          )}
        </>
      )}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  useLassoSelection hook                                            */
/* ------------------------------------------------------------------ */

export function useLassoSelection(
  points: Array<{ x: number; y: number; id: string }>,
  lassoPolygon: LassoPoint[] | null,
): string[] {
  return useMemo(() => {
    if (!lassoPolygon || lassoPolygon.length < 3) return [];
    return points
      .filter((p) => pointInPolygon(p.x, p.y, lassoPolygon))
      .map((p) => p.id);
  }, [points, lassoPolygon]);
}
