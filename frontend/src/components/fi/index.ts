/* ------------------------------------------------------------------ */
/*  Fixed Income Components — Barrel Export                            */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

export { KeySpreadsPanel } from './KeySpreadsPanel';
export type { KeySpreadsPanelProps, SpreadRow } from './KeySpreadsPanel';

export { TreasuryAuctionCalendar } from './TreasuryAuctionCalendar';
export type { TreasuryAuctionCalendarProps, AuctionRecord } from './TreasuryAuctionCalendar';

export { NewIssueTable } from './NewIssueTable';
export type { NewIssueTableProps, NewIssue } from './NewIssueTable';

export { BondTermsPanel } from './BondTermsPanel';
export type {
  BondTermsPanelProps,
  BondTerms,
  CallScheduleEntry,
  CovenantEntry,
} from './BondTermsPanel';

export { SpreadHistoryChart } from './SpreadHistoryChart';
export type { SpreadHistoryChartProps, SpreadDataPoint } from './SpreadHistoryChart';
