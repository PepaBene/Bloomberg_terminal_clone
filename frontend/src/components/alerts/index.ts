/* ------------------------------------------------------------------ */
/*  Alerts Components — Barrel Export                                  */
/*  Bloomberg Data Fabric Terminal                                     */
/* ------------------------------------------------------------------ */

export { AlertInbox } from './AlertInbox';
export type { AlertInboxProps, Alert } from './AlertInbox';

export { AlertRuleEditor } from './AlertRuleEditor';
export type {
  AlertRuleEditorProps,
  AlertRuleConfig,
  AlertRuleCondition,
} from './AlertRuleEditor';

export { AlertTimeline } from './AlertTimeline';
export type { AlertTimelineProps, TimelineAlert } from './AlertTimeline';

export { WatchlistManager } from './WatchlistManager';
export type { WatchlistManagerProps, WatchlistEntity } from './WatchlistManager';

export { EarningsCalendarWidget } from './EarningsCalendarWidget';
export type { EarningsCalendarWidgetProps, EarningsEvent } from './EarningsCalendarWidget';
