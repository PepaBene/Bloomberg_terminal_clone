/* ------------------------------------------------------------------ */
/*  Chart Component Library — Barrel Export                           */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

// Shared theme
export { CHART_THEME, seriesColor } from './chartTheme';

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
