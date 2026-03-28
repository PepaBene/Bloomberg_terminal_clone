import { useCallback } from 'react';
import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ComparisonSeries {
  key: string;
  name: string;
  color: string;
  visible: boolean;
}

export interface ComparisonLegendProps {
  series: ComparisonSeries[];
  onToggle: (key: string) => void;
}

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'row',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: 12,
};

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  cursor: 'pointer',
  border: 'none',
  background: 'none',
  padding: 0,
  fontFamily: CHART_THEME.fonts.ui,
  fontSize: 11,
  lineHeight: 1,
  userSelect: 'none',
};

const dotStyle: React.CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: '50%',
  flexShrink: 0,
  transition: 'opacity 120ms ease',
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ComparisonLegend({ series, onToggle }: ComparisonLegendProps) {
  const handleToggle = useCallback(
    (key: string) => () => {
      onToggle(key);
    },
    [onToggle],
  );

  return (
    <div style={containerStyle} role="group" aria-label="Series legend">
      {series.map((s) => (
        <button
          key={s.key}
          type="button"
          onClick={handleToggle(s.key)}
          style={{
            ...itemStyle,
            opacity: s.visible ? 1 : 0.3,
            color: s.visible
              ? CHART_THEME.colors.textSecondary
              : CHART_THEME.colors.textTertiary,
          }}
          aria-pressed={s.visible}
          title={s.visible ? `Hide ${s.name}` : `Show ${s.name}`}
        >
          <span
            style={{
              ...dotStyle,
              backgroundColor: s.color,
              opacity: s.visible ? 1 : 0.3,
            }}
          />
          {s.name}
        </button>
      ))}
    </div>
  );
}
