/* ------------------------------------------------------------------ */
/*  Chart Component Library — Barrel Export                           */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

// Shared theme
export { CHART_THEME, seriesColor } from './chartTheme';

// Rich tooltip — shared across all chart types
export { ChartTooltip } from './ChartTooltip';
export type {
  ChartTooltipProps,
  ChartTooltipChange,
  ChartTooltipPercentile,
  ChartTooltipBenchmark,
  ChartTooltipSource,
  ChartTooltipSeriesItem,
} from './ChartTooltip';

// Time-series line / area chart (Recharts)
export { TimeSeriesChart } from './TimeSeriesChart';
export type {
  TimeSeriesChartProps,
  TimeSeriesSeries,
  TimeSeriesEvent,
} from './TimeSeriesChart';

// Candlestick / OHLC chart (TradingView Lightweight Charts)
export { CandlestickChart } from './CandlestickChart';
export type {
  CandlestickChartProps,
  CandlestickDataPoint,
} from './CandlestickChart';

// Bar chart — grouped / stacked (Recharts)
export { BarChartComponent } from './BarChart';
export type {
  BarChartComponentProps,
  BarDefinition,
} from './BarChart';

// Donut / pie chart — allocation & composition (Recharts)
export { DonutChart } from './DonutChart';
export type {
  DonutChartProps,
  DonutDataPoint,
} from './DonutChart';

// Heatmap — correlation matrix, calendar returns (SVG + D3)
export { HeatmapChart } from './HeatmapChart';
export type {
  HeatmapChartProps,
  HeatmapDataPoint,
} from './HeatmapChart';

// Yield curve — specialized fixed-income visualization (Recharts)
export { YieldCurveChart } from './YieldCurveChart';
export type {
  YieldCurveChartProps,
  YieldCurvePoint,
} from './YieldCurveChart';

// Range selector — time range toggle for time-series charts
export { RangeSelector } from './RangeSelector';
export type { RangeSelectorProps } from './RangeSelector';

// Event overlay — markers for earnings, filings, dividends, etc.
export { EventOverlay } from './EventOverlay';
export type { EventOverlayProps, ChartEvent } from './EventOverlay';

// Comparison legend — toggleable multi-series legend
export { ComparisonLegend } from './ComparisonLegend';
export type { ComparisonLegendProps, ComparisonSeries } from './ComparisonLegend';

// Linked crosshairs — synchronized crosshair across multiple charts
export {
  CrosshairProvider,
  useLinkedCrosshair,
  CrosshairLine,
  useCrosshairMouseHandler,
} from './LinkedCrosshairs';
export type {
  CrosshairContextValue,
  CrosshairProviderProps,
  CrosshairLineProps,
} from './LinkedCrosshairs';

// Gauge chart — semi-circle gauge for quality scores
export { GaugeChart } from './GaugeChart';
export type { GaugeChartProps, GaugeThreshold } from './GaugeChart';

// Score breakdown — detailed sub-score panel
export { ScoreBreakdown } from './ScoreBreakdown';
export type { ScoreBreakdownProps, ScoreItem } from './ScoreBreakdown';

// Lasso selection — free-form polygon selection overlay for scatter plots
export { LassoSelection, useLassoSelection } from './LassoSelection';
export type { LassoPoint, LassoSelectionProps } from './LassoSelection';

// Waterfall chart — financial bridge / EBITDA bridge visualization
export { WaterfallChart } from './WaterfallChart';
export type { WaterfallBar, WaterfallChartProps } from './WaterfallChart';

// Monte Carlo chart — probability distribution histogram for scenario outputs
export { MonteCarloChart } from './MonteCarloChart';
export type { MonteCarloChartProps } from './MonteCarloChart';

// Order book depth — cumulative bid/ask step-area chart
export { OrderBookDepthChart } from './OrderBookDepthChart';
export type { OrderBookDepthChartProps, OrderBookLevel } from './OrderBookDepthChart';

// Volume profile — horizontal volume-by-price histogram with point of control
export { VolumeProfileChart } from './VolumeProfileChart';
export type { VolumeProfileChartProps, VolumeProfileLevel } from './VolumeProfileChart';
