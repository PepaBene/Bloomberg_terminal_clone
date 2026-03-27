/**
 * Shared chart theme constants for the Bloomberg Data Fabric terminal.
 *
 * All color values mirror the design tokens defined in src/styles/tokens.css
 * so that charts are visually consistent with the rest of the terminal UI.
 */

export const CHART_THEME = {
  colors: {
    /** Grid lines — surface-border at 30 % opacity */
    grid: 'rgba(30, 37, 46, 0.3)',
    /** Axis tick / label text — text-secondary */
    axis: '#8A96A3',

    tooltip: {
      /** surface-raised */
      bg: '#111519',
      /** surface-border */
      border: '#1E252E',
      /** text-primary */
      text: '#E8EDF2',
      /** text-secondary */
      label: '#8A96A3',
    },

    /** Categorical chart palette (chart-1 … chart-8) */
    series: [
      '#3B82F6',
      '#2DB87D',
      '#D4A843',
      '#A855F7',
      '#E05252',
      '#06B6D4',
      '#F97316',
      '#84CC16',
    ] as const,

    /** signal-positive — gains, growth */
    positive: '#2DB87D',
    /** signal-negative — losses, decline */
    negative: '#E05252',
    /** signal-neutral — unchanged, baseline reference */
    neutral: '#5B7FA6',
    /** signal-warning */
    warning: '#E0923A',
    /** signal-highlight */
    highlight: '#D4A843',

    /** accent-primary */
    accent: '#3B82F6',
    /** accent glow (15 % opacity) */
    accentGlow: 'rgba(59, 130, 246, 0.15)',

    /** Surface tokens used for chart backgrounds */
    surfaceBase: '#0C0F12',
    surfaceRaised: '#111519',
    surfaceBorder: '#1E252E',
    surfaceBorderStrong: '#2A3440',

    /** text-primary */
    textPrimary: '#E8EDF2',
    /** text-secondary */
    textSecondary: '#8A96A3',
    /** text-tertiary */
    textTertiary: '#545F6B',
  },

  fonts: {
    /** JetBrains Mono — all numerical data */
    data: "'JetBrains Mono', 'Fira Code', monospace",
    /** IBM Plex Sans — labels, prose, navigation */
    ui: "'IBM Plex Sans', 'Helvetica Neue', sans-serif",
  },

  /** shadow-float token */
  shadowFloat: '0 4px 24px rgba(0,0,0,0.65), 0 0 1px rgba(0,0,0,0.4)',
} as const;

/** Type-safe accessor for the i-th series color (wraps around) */
export function seriesColor(index: number): string {
  return CHART_THEME.colors.series[
    index % CHART_THEME.colors.series.length
  ] as string;
}
