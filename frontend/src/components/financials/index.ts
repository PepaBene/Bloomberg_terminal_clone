/* ------------------------------------------------------------------ */
/*  Financial Statement Components — Barrel Export                     */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

// Hierarchical financial statement table with collapse/expand
export { StatementTable } from './StatementTable';
export type { StatementTableProps, StatementRowData } from './StatementTable';

// Individual row renderer
export { StatementRow } from './StatementRow';
export type { StatementRowProps } from './StatementRow';

// Period mode toggle (Annual / Quarterly) + count selector
export { PeriodSelector } from './PeriodSelector';
export type { PeriodSelectorProps } from './PeriodSelector';

// Line item pop-up chart
export { LineItemChart } from './LineItemChart';
export type { LineItemChartProps, LineItemDataPoint } from './LineItemChart';

// Common-size toggle
export { CommonSizeToggle } from './CommonSizeToggle';
export type { CommonSizeToggleProps } from './CommonSizeToggle';
