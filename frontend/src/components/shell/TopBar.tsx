import { useSecurityStore } from '@/stores/securityContext';
import { useAlertsStore } from '@/stores/alertsState';
import { useNavigationStore } from '@/stores/navigationHistory';

export function TopBar() {
  const primary = useSecurityStore(s => s.primary);
  const unread = useAlertsStore(s => s.unread);
  const recent = useNavigationStore(s => s.recent(5));

  return (
    <header className="flex items-center h-10 px-3 bg-surface-base border-b border-surface-border gap-3">
      {/* Logo */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-6 h-6 bg-accent-primary rounded flex items-center justify-center text-xs font-bold text-white">
          B
        </div>
        <span className="text-text-secondary text-xs font-ui hidden lg:inline">DATA FABRIC</span>
      </div>

      {/* Search trigger */}
      <button
        className="flex-1 max-w-xl h-7 px-3 bg-surface-void border border-surface-border rounded text-text-tertiary text-xs text-left hover:border-accent-primary transition-colors"
        onClick={() => {/* TODO: open command bar */}}
      >
        <span className="font-data">/ </span>
        <span className="font-ui">Search securities, commands...</span>
      </button>

      {/* Active security breadcrumb */}
      <div className="flex items-center gap-2">
        {primary && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-surface-raised rounded">
            <span className="text-accent-primary font-data text-xs font-semibold">{primary.ticker}</span>
            <span className="text-text-secondary text-xs truncate max-w-32">{primary.name}</span>
          </div>
        )}
      </div>

      {/* Recent history */}
      <div className="hidden xl:flex items-center gap-1">
        {recent.slice(0, 3).map((sec, i) => (
          <button key={i} className="text-text-tertiary text-xs font-data hover:text-text-primary px-1">
            {sec.ticker}
          </button>
        ))}
      </div>

      <div className="flex-1" />

      {/* Alerts badge */}
      <button className="relative p-1.5 hover:bg-surface-overlay rounded">
        <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unread.length > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-signal-negative rounded-full text-[9px] font-bold text-white flex items-center justify-center">
            {unread.length > 99 ? '99+' : unread.length}
          </span>
        )}
      </button>

      {/* User menu */}
      <div className="w-7 h-7 bg-surface-overlay rounded-full flex items-center justify-center text-text-secondary text-xs font-bold">
        U
      </div>
    </header>
  );
}
