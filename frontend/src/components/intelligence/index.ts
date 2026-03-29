/* ------------------------------------------------------------------ */
/*  Intelligence Components — Barrel Export                            */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

export { SentimentGauge } from './SentimentGauge';
export type { SentimentGaugeProps } from './SentimentGauge';

export { FilingDiffViewer } from './FilingDiffViewer';
export type { FilingDiffViewerProps, DiffSection, DiffChange } from './FilingDiffViewer';

export { InsiderActivityTable } from './InsiderActivityTable';
export type {
  InsiderActivityTableProps,
  InsiderTransaction,
  InsiderSignal,
} from './InsiderActivityTable';

export { GovernanceScorecard } from './GovernanceScorecard';
export type { GovernanceScorecardProps, RedFlag } from './GovernanceScorecard';

export { EarningsSurpriseChart } from './EarningsSurpriseChart';
export type { EarningsSurpriseChartProps, EarningsSurprise } from './EarningsSurpriseChart';

export { TranscriptViewer } from './TranscriptViewer';
export type {
  TranscriptViewerProps,
  TranscriptSection,
  TranscriptParagraph,
  ToneScores,
} from './TranscriptViewer';

export { CompanyIntelCard } from './CompanyIntelCard';
export type { CompanyIntelCardProps, IntelModule } from './CompanyIntelCard';
