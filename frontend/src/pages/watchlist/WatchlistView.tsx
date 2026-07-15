// ---------------------------------------------------------------------------
// Watchlist View — Watchlist Management, Monitoring Alerts, Earnings Calendar
// ---------------------------------------------------------------------------
import { useState, useCallback, useRef, useEffect } from 'react';
import { WatchlistManager, EarningsCalendarWidget } from '@/components/alerts';
import type { WatchlistEntity, EarningsEvent } from '@/components/alerts';
import { useWatchlists } from '@/hooks';
import { api } from '@/api/client';
import { WATCHLISTS } from '@/api/endpoints';
import { useToastStore } from '@/stores/toastStore';

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
const SEARCH_SUGGESTIONS: { ticker: string; name: string }[] = [];

// --- Component Data ----------------------------------------------------------

const initialEntities: WatchlistEntity[] = [];

const earningsEvents: EarningsEvent[] = earningsCalendar.map((e, i) => ({
  id: `ec-${i}`,
  date: e.date,
  ticker: e.ticker,
  companyName: e.name,
  expectedEps: parseFloat(e.epsEst.replace('$', '')),
  time: e.time as EarningsEvent['time'],
}));

export default function WatchlistView() {
  const [entities, setEntities] = useState<WatchlistEntity[]>(initialEntities);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // --- Backend sync via usePortfolioWatchlists hooks -------------------------
  const { data: apiWatchlists } = useWatchlists() as { data: ApiWatchlist[] | undefined };
  const defaultWatchlistId = apiWatchlists?.[0]?.id;

  // Focus input when dialog opens
  useEffect(() => {
    if (showSearch) searchInputRef.current?.focus();
  }, [showSearch]);

  const filteredSuggestions = SEARCH_SUGGESTIONS.filter(
    (s) =>
      !entities.some((e) => e.ticker === s.ticker) &&
      (s.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.name.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const addEntity = useCallback(async (ticker: string, name: string) => {
    setEntities((prev) => [
      ...prev,
      {
        id: `w-${Date.now()}`,
        ticker,
        name,
        alertsEnabled: { price: true, filing: false, earnings: false, score: false },
      },
    ]);
    setShowSearch(false);
    setSearchQuery('');
    if (defaultWatchlistId) {
      try {
        await api.post(WATCHLISTS.addItem(defaultWatchlistId), { ticker, name });
      } catch (err) {
        console.error('[WatchlistView] Failed to add watchlist item', err);
        useToastStore.getState().showToast(`Failed to save ${ticker} to your watchlist.`);
      }
    }
  }, [defaultWatchlistId]);

  const handleAdd = useCallback(() => {
    setShowSearch(true);
  }, []);

  const handleRemove = useCallback(async (id: string) => {
    setEntities((prev) => prev.filter((e) => e.id !== id));
    if (defaultWatchlistId) {
      try {
        await api.delete(WATCHLISTS.removeItem(defaultWatchlistId, id));
      } catch (err) {
        console.error('[WatchlistView] Failed to remove watchlist item', err);
        useToastStore.getState().showToast('Failed to remove item from your watchlist.');
      }
    }
  }, [defaultWatchlistId]);

  const handleReorder = useCallback((fromIdx: number, toIdx: number) => {
    setEntities((prev) => {
      const next = [...prev];
      const [item] = next.splice(fromIdx, 1);
      if (item) next.splice(toIdx, 0, item);
      return next;
    });
  }, []);

  const handleToggleAlert = useCallback((id: string, alertType: keyof WatchlistEntity['alertsEnabled']) => {
    setEntities((prev) =>
      prev.map((e) =>
        e.id === id ? { ...e, alertsEnabled: { ...e.alertsEnabled, [alertType]: !e.alertsEnabled[alertType] } } : e,
      ),
    );
  }, []);

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
                  key={s.ticker}
                  onClick={() => addEntity(s.ticker, s.name)}
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
