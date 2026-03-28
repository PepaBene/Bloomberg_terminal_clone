import { useState, useCallback, useMemo } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface UseKeyboardNavigationOptions {
  /** Total number of navigable items. */
  itemCount: number;
  /** Fires when Enter is pressed on the active item. */
  onSelect?: (index: number) => void;
  /** Fires when Right arrow is pressed (e.g. expand / drill-in). */
  onExpand?: (index: number) => void;
  /** Set to false to temporarily disable keyboard handling. */
  enabled?: boolean;
}

export interface UseKeyboardNavigationReturn {
  /** Currently focused item index (0-based). */
  activeIndex: number;
  /** Imperatively set the active index. */
  setActiveIndex: (i: number) => void;
  /** Spread onto the scrollable container element. */
  containerProps: {
    tabIndex: number;
    onKeyDown: (e: React.KeyboardEvent) => void;
    role: string;
  };
  /** Spread onto each navigable item (pass its index). */
  getItemProps: (index: number) => {
    'aria-selected': boolean;
    'data-active': boolean;
  };
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

/** Number of items to jump when Page Up / Page Down is pressed. */
const PAGE_SIZE = 10;

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function useKeyboardNavigation({
  itemCount,
  onSelect,
  onExpand,
  enabled = true,
}: UseKeyboardNavigationOptions): UseKeyboardNavigationReturn {
  const [activeIndex, setActiveIndex] = useState(0);

  /* ---- clamp helper ---- */
  const clamp = useCallback(
    (n: number) => {
      if (itemCount === 0) return 0;
      // Wrap around at bounds
      if (n < 0) return itemCount - 1;
      if (n >= itemCount) return 0;
      return n;
    },
    [itemCount],
  );

  /* ---- keydown handler ---- */
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!enabled || itemCount === 0) return;

      switch (e.key) {
        case 'ArrowDown': {
          e.preventDefault();
          setActiveIndex((prev) => clamp(prev + 1));
          break;
        }
        case 'ArrowUp': {
          e.preventDefault();
          setActiveIndex((prev) => clamp(prev - 1));
          break;
        }
        case 'Home': {
          e.preventDefault();
          setActiveIndex(0);
          break;
        }
        case 'End': {
          e.preventDefault();
          setActiveIndex(itemCount - 1);
          break;
        }
        case 'PageDown': {
          e.preventDefault();
          setActiveIndex((prev) => clamp(Math.min(prev + PAGE_SIZE, itemCount - 1)));
          break;
        }
        case 'PageUp': {
          e.preventDefault();
          setActiveIndex((prev) => clamp(Math.max(prev - PAGE_SIZE, 0)));
          break;
        }
        case 'Enter': {
          e.preventDefault();
          onSelect?.(activeIndex);
          break;
        }
        case 'ArrowRight': {
          e.preventDefault();
          onExpand?.(activeIndex);
          break;
        }
        default:
          break;
      }
    },
    [enabled, itemCount, clamp, activeIndex, onSelect, onExpand],
  );

  /* ---- container props ---- */
  const containerProps = useMemo(
    () => ({
      tabIndex: 0,
      onKeyDown,
      role: 'listbox' as const,
    }),
    [onKeyDown],
  );

  /* ---- per-item prop factory ---- */
  const getItemProps = useCallback(
    (index: number) => ({
      'aria-selected': index === activeIndex,
      'data-active': index === activeIndex,
    }),
    [activeIndex],
  );

  return { activeIndex, setActiveIndex, containerProps, getItemProps };
}
