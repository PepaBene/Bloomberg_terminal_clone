import { useCallback } from 'react';
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
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DEFAULT_RANGES = ['1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y', 'Max'] as const;

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
  gap: 2,
};

const baseButtonStyle: React.CSSProperties = {
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
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RangeSelector({
  ranges = DEFAULT_RANGES as unknown as string[],
  active,
  onChange,
}: RangeSelectorProps) {
  const handleClick = useCallback(
    (range: string) => () => {
      if (range !== active) onChange(range);
    },
    [active, onChange],
  );

  return (
    <div style={containerStyle} role="group" aria-label="Time range selector">
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
  );
}
