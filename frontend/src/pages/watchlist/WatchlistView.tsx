// ---------------------------------------------------------------------------
// Watchlist View — Watchlist Management, Monitoring Alerts, Earnings Calendar
// ---------------------------------------------------------------------------
import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { WatchlistManager, EarningsCalendarWidget } from '@/components/alerts';
import type { WatchlistEntity, EarningsEvent } from '@/components/alerts';
import { useWatchlists, useCreateWatchlist } from '@/hooks';
import { useSecuritySearch } from '@/api/hooks/useSecurities';
import { api } from '@/api/client';
import { WATCHLISTS } from '@/api/endpoints';
import { useToastStore } from '@/stores/toastStore';
import type { SecuritySearchResult } from '@/types/security';

// GET /v4/portfolios/watchlists/{id} (src/schemas/watchlist_schema.py)
interface ApiWatchlistEntity {
  entity_id: string;
  legal_name: string | null;
  added_date: string | null;
}
interface ApiWatchlistDetail {
  id: string;
  name: string;
  description: string | null;
  entities: ApiWatchlistEntity[];
}

// WatchlistResponse (src/schemas/watchlist_schema.py) -- real shape returned
// by GET /v4/portfolios/watchlists (src/api/routers/portfolio_watchlists.py)
// (P4-F-022 fix). Replaces the `as any` cast that read a nonexistent
// `.watchlists` wrapper -- the real route returns a plain array.
interface ApiWatchlist {
  id: string;
  name: string;
  description: string | null;
}

const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

// --- Empty fallback (P4-F-016) -----------------------------------------------
// We deliberately avoid hardcoded AAPL/MSFT/NVDA holdings, an Apple
// earnings date, and a fake search-autocomplete list — those rendered as
// "live" content for any user who hadn't built a watchlist yet. The
// real search endpoint provides autocomplete; the watchlist API
// provides holdings + earnings.

const earningsCalendar: { date: string; ticker: string; name: string; time: string; epsEst: string; impliedMove: string }[] = [];

// --- Component Data ----------------------------------------------------------

const earningsEvents: EarningsEvent[] = earningsCalendar.map((e, i) => ({
  id: `ec-${i}`,
  date: e.date,
  ticker: e.ticker,
  companyName: e.name,
  expectedEps: parseFloat(e.epsEst.replace('$', '')),
  time: e.time as EarningsEvent['time'],
}));

export default function WatchlistView() {
  const [addedThisSession, setAddedThisSession] = useState<Record<string, { ticker: string; name: string }>>({});
  const [removedThisSession, setRemovedThisSession] = useState<Set<string>>(new Set());
  const [alertOverrides, setAlertOverrides] = useState<Record<string, Partial<WatchlistEntity['alertsEnabled']>>>({});
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // --- Backend sync via usePortfolioWatchlists hooks -------------------------
  const { data: apiWatchlists } = useWatchlists() as { data: ApiWatchlist[] | undefined };
  const createWatchlist = useCreateWatchlist();
  const [pendingWatchlistId, setPendingWatchlistId] = useState<string | undefined>(undefined);
  // A brand-new user has zero watchlists (GET returns `[]`) -- there was never
  // an onboarding step to create one, so "+ Add Entity" silently no-op'd
  // forever (defaultWatchlistId was always undefined). Lazily create a
  // default watchlist the first time the user actually adds something.
  const defaultWatchlistId = apiWatchlists?.[0]?.id ?? pendingWatchlistId;

  // The list endpoint only returns id/name/description -- entities live under
  // the detail endpoint. This was never fetched at all before, so even a
  // successfully-saved watchlist item vanished from the UI on next reload
  // (the list only ever grew from client-side state for the current tab).
  const { data: watchlistDetail } = useQuery<ApiWatchlistDetail>({
    queryKey: ['watchlists', defaultWatchlistId, 'detail'],
    queryFn: () => api.get(WATCHLISTS.detail(defaultWatchlistId as string)),
    enabled: !!defaultWatchlistId,
  });

  // Merge persisted entities with this-session additions/removals so the UI
  // updates immediately without waiting on a refetch, while still reflecting
  // what's actually saved once one lands. The backend only returns
  // entity_id/legal_name (no ticker) -- tickers for freshly-added-this-session
  // rows come from the search result the user picked; persisted rows that
  // predate this session show "--" for ticker rather than a wrong guess.
  const entities: WatchlistEntity[] = useMemo(() => {
    const defaultAlerts = { price: true, filing: false, earnings: false, score: false };
    const withOverrides = (id: string) => ({ ...defaultAlerts, ...alertOverrides[id] });
    const persisted = (watchlistDetail?.entities ?? [])
      .filter((e) => !removedThisSession.has(e.entity_id))
      .map((e) => ({
        id: e.entity_id,
        ticker: addedThisSession[e.entity_id]?.ticker ?? '—',
        name: addedThisSession[e.entity_id]?.name ?? e.legal_name ?? '—',
        alertsEnabled: withOverrides(e.entity_id),
      }));
    const persistedIds = new Set(persisted.map((e) => e.id));
    const sessionOnly = Object.entries(addedThisSession)
      .filter(([entityId]) => !persistedIds.has(entityId) && !removedThisSession.has(entityId))
      .map(([entityId, v]) => ({
        id: entityId,
        ticker: v.ticker,
        name: v.name,
        alertsEnabled: withOverrides(entityId),
      }));
    return [...persisted, ...sessionOnly];
  }, [watchlistDetail, addedThisSession, removedThisSession, alertOverrides]);

  // Focus input when dialog opens
  useEffect(() => {
    if (showSearch) searchInputRef.current?.focus();
  }, [showSearch]);

  const { data: searchData } = useSecuritySearch(searchQuery, { enabled: showSearch && searchQuery.trim().length > 0 });
  const filteredSuggestions = (
    (searchData as { results?: SecuritySearchResult[] } | undefined)?.results ?? []
  ).filter((s) => !entities.some((e) => e.ticker === s.ticker));

  const addEntity = useCallback(async (security: SecuritySearchResult) => {
    setShowSearch(false);
    setSearchQuery('');
    try {
      let watchlistId = defaultWatchlistId;
      if (!watchlistId) {
        const created = await createWatchlist.mutateAsync({ name: 'My Watchlist' } as never) as ApiWatchlist;
        watchlistId = created.id;
        setPendingWatchlistId(created.id);
      }
      // Watchlist entities are keyed by entity_id, not security_id -- resolve
      // via the securities detail endpoint's issuer_entity_id (same pattern
      // used for the global search -> Company page flow).
      const detail = await api.get<{ issuer_entity_id?: string | null }>(`/v1/securities/${security.security_id}`);
      const entityId = detail?.issuer_entity_id;
      if (!entityId) {
        useToastStore.getState().showToast(`${security.ticker} has no linked issuer entity to watch.`);
        return;
      }
      setAddedThisSession((prev) => ({ ...prev, [entityId]: { ticker: security.ticker, name: security.name } }));
      setRemovedThisSession((prev) => {
        if (!prev.has(entityId)) return prev;
        const next = new Set(prev);
        next.delete(entityId);
        return next;
      });
      await api.post(WATCHLISTS.addItem(watchlistId, entityId));
    } catch (err) {
      console.error('[WatchlistView] Failed to add watchlist item', err);
      useToastStore.getState().showToast(`Failed to save ${security.ticker} to your watchlist.`);
    }
  }, [defaultWatchlistId, createWatchlist]);

  const handleAdd = useCallback(() => {
    setShowSearch(true);
  }, []);

  const handleRemove = useCallback(async (entityId: string) => {
    setRemovedThisSession((prev) => new Set(prev).add(entityId));
    if (defaultWatchlistId) {
      try {
        await api.delete(WATCHLISTS.removeItem(defaultWatchlistId, entityId));
      } catch (err) {
        console.error('[WatchlistView] Failed to remove watchlist item', err);
        useToastStore.getState().showToast('Failed to remove item from your watchlist.');
      }
    }
  }, [defaultWatchlistId]);

  // Reordering was always a pure client-array mutation with nothing backing
  // it server-side (no watchlist "order" field or endpoint exists) -- it
  // reset on every reload before this change too, so dropping it loses no
  // real functionality now that `entities` is derived rather than owned
  // local state.
  const handleReorder = useCallback((_fromIdx: number, _toIdx: number) => {}, []);

  const handleToggleAlert = useCallback((id: string, alertType: keyof WatchlistEntity['alertsEnabled']) => {
    setAlertOverrides((prev) => {
      const current = entities.find((e) => e.id === id)?.alertsEnabled;
      const currentValue = prev[id]?.[alertType] ?? current?.[alertType] ?? false;
      return { ...prev, [id]: { ...prev[id], [alertType]: !currentValue } };
    });
  }, [entities]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Watchlist</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Core Holdings &mdash; {entities.length} securities monitored</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* WatchlistManager — replaces inline table */}
        <WatchlistManager
          entities={entities}
          onAdd={handleAdd}
          onRemove={handleRemove}
          onReorder={handleReorder}
          onToggleAlert={handleToggleAlert}
        />
        {/* EarningsCalendarWidget — replaces inline earnings table */}
        <EarningsCalendarWidget
          events={earningsEvents}
          watchlistTickers={entities.map((e) => e.ticker)}
        />
      </div>

      {/* Entity Search Dialog */}
      {showSearch && (
        <div
          onClick={() => { setShowSearch(false); setSearchQuery(''); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            paddingTop: '15vh', zIndex: 1000,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '420px', background: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)', borderRadius: '8px',
              padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px',
            }}
          >
            <h3 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
              Add Security to Watchlist
            </h3>
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by ticker or name..."
              style={{
                fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
                padding: '8px 12px', borderRadius: '4px',
                border: '1px solid var(--color-surface-border)',
                background: 'var(--color-surface-raised)', color: 'var(--color-text-primary)',
                outline: 'none',
              }}
            />
            <div style={{ maxHeight: '240px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {filteredSuggestions.length === 0 && (
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: '8px' }}>
                  No results found
                </span>
              )}
              {filteredSuggestions.map((s) => (
                <div
                  key={s.security_id}
                  onClick={() => addEntity(s)}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 10px', borderRadius: '4px', cursor: 'pointer',
                    background: 'transparent',
                  }}
                  onMouseOver={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)'; }}
                  onMouseOut={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                >
                  <div>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{s.ticker}</span>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>{s.name}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>+ Add</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
