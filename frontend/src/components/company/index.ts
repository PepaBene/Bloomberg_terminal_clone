/* ------------------------------------------------------------------ */
/*  Company Components — Barrel Export                                 */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

// Key metrics grid (8 KPI cards)
export { KeyMetricsGrid } from './KeyMetricsGrid';
export type { KeyMetricsGridProps, MetricItem } from './KeyMetricsGrid';

// DuPont decomposition + multiples history
export { RatioDashboard } from './RatioDashboard';
export type { RatioDashboardProps, DuPontData, MultiplesPoint } from './RatioDashboard';

// Top 10 institutional holders
export { OwnershipSummary } from './OwnershipSummary';
export type { OwnershipSummaryProps, Holder } from './OwnershipSummary';

// Credit / leverage / coverage / liquidity ratios
export { CreditRatioPanel } from './CreditRatioPanel';
export type { CreditRatioPanelProps, CreditRatio } from './CreditRatioPanel';

// Bond inventory table
export { BondInventoryTable } from './BondInventoryTable';
export type { BondInventoryTableProps, BondRecord } from './BondInventoryTable';

// Maturity wall bar chart
export { MaturityWallChart } from './MaturityWallChart';
export type { MaturityWallChartProps, MaturityBucket } from './MaturityWallChart';

// Equity vs credit divergence dual-axis chart
export { EquityCreditDivergence } from './EquityCreditDivergence';
export type { EquityCreditDivergenceProps, EquityCreditPoint } from './EquityCreditDivergence';
