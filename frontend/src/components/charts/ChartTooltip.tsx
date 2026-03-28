import { CHART_THEME } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ChartTooltipChange {
  value: string;
  direction: 'up' | 'down' | 'flat';
  period?: string;
}

export interface ChartTooltipPercentile {
  rank: number;
  group: string;
}

export interface ChartTooltipBenchmark {
  label: string;
  value: string;
}

export interface ChartTooltipSource {
  label: string;
  href?: string;
}

export interface ChartTooltipSeriesItem {
  name: string;
  value: string;
  color: string;
}

export interface ChartTooltipProps {
  title: string;
  value: string;
  change?: ChartTooltipChange;
  secondaryChange?: ChartTooltipChange;
  percentile?: ChartTooltipPercentile;
  benchmark?: ChartTooltipBenchmark;
  source?: ChartTooltipSource;
  series?: ChartTooltipSeriesItem[];
}

/* ------------------------------------------------------------------ */
/*  Style constants                                                    */
/* ------------------------------------------------------------------ */

const STYLES = {
  container: {
    background: CHART_THEME.colors.tooltip.bg,
    border: `1px solid ${CHART_THEME.colors.surfaceBorderStrong}`,
    borderRadius: 4,
    padding: '10px 12px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
    pointerEvents: 'none' as const,
    minWidth: 160,
  },
  title: {
    fontFamily: CHART_THEME.fonts.ui,
    fontSize: 11,
    color: CHART_THEME.colors.tooltip.label,
    marginBottom: 0,
    lineHeight: 1.4,
  },
  separator: {
    height: 1,
    background: CHART_THEME.colors.surfaceBorder,
    margin: '6px 0',
    border: 'none',
  },
  value: {
    fontFamily: CHART_THEME.fonts.data,
    fontSize: 15,
    fontWeight: 600 as const,
    color: CHART_THEME.colors.tooltip.text,
    fontVariantNumeric: 'tabular-nums' as const,
    lineHeight: 1.4,
  },
  changePositive: {
    color: CHART_THEME.colors.positive,
  },
  changeNegative: {
    color: CHART_THEME.colors.negative,
  },
  changeFlat: {
    color: CHART_THEME.colors.neutral,
  },
  changeText: {
    fontFamily: CHART_THEME.fonts.data,
    fontSize: 11,
    fontVariantNumeric: 'tabular-nums' as const,
    lineHeight: 1.5,
  },
  percentile: {
    fontFamily: CHART_THEME.fonts.ui,
    fontSize: 10,
    color: CHART_THEME.colors.tooltip.label,
    lineHeight: 1.5,
  },
  benchmark: {
    fontFamily: CHART_THEME.fonts.data,
    fontSize: 11,
    color: CHART_THEME.colors.tooltip.label,
    fontVariantNumeric: 'tabular-nums' as const,
    lineHeight: 1.5,
  },
  sourceLink: {
    fontFamily: CHART_THEME.fonts.ui,
    fontSize: 10,
    color: CHART_THEME.colors.accent,
    textDecoration: 'none',
    lineHeight: 1.5,
  },
  seriesRow: {
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: 6,
    fontFamily: CHART_THEME.fonts.data,
    fontSize: 12,
    color: CHART_THEME.colors.tooltip.text,
    lineHeight: 1.6,
  },
  seriesDot: {
    width: 8,
    height: 8,
    borderRadius: 2,
    flexShrink: 0,
  },
  seriesName: {
    fontFamily: CHART_THEME.fonts.ui,
    color: CHART_THEME.colors.tooltip.label,
  },
  seriesValue: {
    marginLeft: 'auto' as const,
    fontVariantNumeric: 'tabular-nums' as const,
  },
} as const;

/* ------------------------------------------------------------------ */
/*  Change indicator helper                                            */
/* ------------------------------------------------------------------ */

function directionArrow(direction: 'up' | 'down' | 'flat'): string {
  switch (direction) {
    case 'up':
      return '\u2191'; // ↑
    case 'down':
      return '\u2193'; // ↓
    case 'flat':
      return '\u2014'; // —
  }
}

function directionColor(direction: 'up' | 'down' | 'flat') {
  switch (direction) {
    case 'up':
      return STYLES.changePositive;
    case 'down':
      return STYLES.changeNegative;
    case 'flat':
      return STYLES.changeFlat;
  }
}

function ChangeDisplay({ change }: { change: ChartTooltipChange }) {
  const colorStyle = directionColor(change.direction);
  return (
    <span style={{ ...STYLES.changeText, ...colorStyle }}>
      {directionArrow(change.direction)} {change.value}
      {change.period ? ` ${change.period}` : ''}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Main tooltip component                                             */
/* ------------------------------------------------------------------ */

export function ChartTooltip({
  title,
  value,
  change,
  secondaryChange,
  percentile,
  benchmark,
  source,
  series,
}: ChartTooltipProps) {
  return (
    <div style={STYLES.container}>
      {/* Title line */}
      <div style={STYLES.title}>{title}</div>

      {/* Separator after title */}
      <div style={STYLES.separator} />

      {/* Primary value + change row */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <span style={STYLES.value}>{value}</span>
        {change && <ChangeDisplay change={change} />}
      </div>

      {/* Secondary change + percentile row */}
      {(secondaryChange || percentile) && (
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginTop: 2 }}>
          {secondaryChange ? <ChangeDisplay change={secondaryChange} /> : <span />}
          {percentile && (
            <span style={STYLES.percentile}>
              {percentile.rank}
              {ordinalSuffix(percentile.rank)} pctl ({percentile.group})
            </span>
          )}
        </div>
      )}

      {/* Series list (multi-series tooltips) */}
      {series && series.length > 0 && (
        <>
          <div style={STYLES.separator} />
          {series.map((s) => (
            <div key={s.name} style={STYLES.seriesRow}>
              <span style={{ ...STYLES.seriesDot, background: s.color }} />
              <span style={STYLES.seriesName}>{s.name}</span>
              <span style={STYLES.seriesValue}>{s.value}</span>
            </div>
          ))}
        </>
      )}

      {/* Benchmark */}
      {benchmark && (
        <>
          <div style={STYLES.separator} />
          <div style={STYLES.benchmark}>
            {benchmark.label}: {benchmark.value}
          </div>
        </>
      )}

      {/* Source link */}
      {source && (
        <>
          <div style={STYLES.separator} />
          {source.href ? (
            <a
              href={source.href}
              target="_blank"
              rel="noopener noreferrer"
              style={STYLES.sourceLink}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'underline';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'none';
              }}
            >
              {'\u2197'} {source.label}
            </a>
          ) : (
            <span style={STYLES.sourceLink}>
              {'\u2197'} {source.label}
            </span>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Utility                                                            */
/* ------------------------------------------------------------------ */

function ordinalSuffix(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'st';
  if (mod10 === 2 && mod100 !== 12) return 'nd';
  if (mod10 === 3 && mod100 !== 13) return 'rd';
  return 'th';
}
