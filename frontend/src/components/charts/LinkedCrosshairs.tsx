import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
  type JSX,
} from 'react';
import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

export interface CrosshairContextValue {
  /** The currently hovered date across all linked charts (null = no hover). */
  activeDate: string | null;
  /** Set or clear the shared crosshair date. */
  setActiveDate: (date: string | null) => void;
}

const CrosshairCtx = createContext<CrosshairContextValue | null>(null);

/* ------------------------------------------------------------------ */
/*  Provider                                                           */
/* ------------------------------------------------------------------ */

export interface CrosshairProviderProps {
  children: ReactNode;
}

export function CrosshairProvider({ children }: CrosshairProviderProps): JSX.Element {
  const [activeDate, setActiveDate] = useState<string | null>(null);

  return (
    <CrosshairCtx.Provider value={{ activeDate, setActiveDate }}>
      {children}
    </CrosshairCtx.Provider>
  );
}

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function useLinkedCrosshair(): CrosshairContextValue {
  const ctx = useContext(CrosshairCtx);
  if (!ctx) {
    throw new Error(
      'useLinkedCrosshair must be used within a <CrosshairProvider>',
    );
  }
  return ctx;
}

/* ------------------------------------------------------------------ */
/*  Visual crosshair line for a single chart                           */
/* ------------------------------------------------------------------ */

export interface CrosshairLineProps {
  chartWidth: number;
  chartHeight: number;
  /** Maps a date string to an x pixel position in the chart area. */
  xScale: (date: string) => number;
}

export function CrosshairLine({
  chartWidth,
  chartHeight,
  xScale,
}: CrosshairLineProps): JSX.Element | null {
  const { activeDate } = useLinkedCrosshair();

  if (!activeDate) return null;

  const x = xScale(activeDate);
  if (x < 0 || x > chartWidth) return null;

  return (
    <svg
      width={chartWidth}
      height={chartHeight}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        overflow: 'visible',
      }}
    >
      <line
        x1={x}
        y1={0}
        x2={x}
        y2={chartHeight}
        stroke={CHART_THEME.colors.textTertiary}
        strokeWidth={1}
        strokeDasharray="4 3"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Helper: onMouseMove handler factory for chart containers           */
/* ------------------------------------------------------------------ */

/**
 * Returns a stable `onMouseMove` handler that resolves the hovered date
 * from an x position and pushes it into the shared crosshair context.
 *
 * Usage:
 * ```tsx
 * const { setActiveDate } = useLinkedCrosshair();
 * const handleMove = useCrosshairMouseHandler(dateFromX, setActiveDate);
 * <div onMouseMove={handleMove} onMouseLeave={() => setActiveDate(null)}>
 * ```
 */
export function useCrosshairMouseHandler(
  dateFromX: (x: number) => string | null,
  setActiveDate: (date: string | null) => void,
) {
  return useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      setActiveDate(dateFromX(x));
    },
    [dateFromX, setActiveDate],
  );
}
