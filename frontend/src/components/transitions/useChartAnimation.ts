import { useState, useEffect, useRef } from 'react';

/**
 * Hook for animating chart data entrance.
 * Returns a slice of data that grows from 0 to full length on mount,
 * creating a left-to-right reveal effect.
 */
export function useChartAnimation<T>(
  data: T[],
  active: boolean,
  duration = 600,
): { animatedData: T[]; isAnimating: boolean } {
  const [progress, setProgress] = useState(active ? 0 : 1);
  const [isAnimating, setIsAnimating] = useState(active);
  const startTimeRef = useRef<number | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      setProgress(1);
      setIsAnimating(false);
      return;
    }

    setProgress(0);
    setIsAnimating(true);
    startTimeRef.current = performance.now();

    function tick(now: number) {
      const elapsed = now - (startTimeRef.current ?? now);
      const t = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setProgress(eased);

      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        setIsAnimating(false);
      }
    }

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current != null) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [active, duration]);

  const visibleCount = Math.ceil(data.length * progress);
  const animatedData = data.slice(0, visibleCount);

  return { animatedData, isAnimating };
}
