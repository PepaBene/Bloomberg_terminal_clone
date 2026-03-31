import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties, KeyboardEvent } from 'react';
import { api } from '@/api/client';

import { QualityScoreCell } from '@/components/ui/QualityScoreCell';

export interface WatchlistPanelProps {
  onSelectSecurity?: (ticker: string) => void;
}

interface WatchlistEntity {
  ticker: string;
  name: string;
  price: number;
  dayChange: number;
  qualityScore?: number;
}

interface Watchlist {
  id: string;
  name: string;
  entities: WatchlistEntity[];
}

export function WatchlistPanel({ onSelectSecurity }: WatchlistPanelProps) {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [newTicker, setNewTicker] = useState<Record<string, string>>({});
  const [newListName, setNewListName] = useState('');
  const [creatingList, setCreatingList] = useState(false);

  const fetchWatchlists = useCallback(() => {
    setLoading(true);
    api
      .get('/v3/portfolios/watchlists')
      .then((data: unknown) => {
        setWatchlists(Array.isArray(data) ? (data as Watchlist[]) : []);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchWatchlists();
  }, [fetchWatchlists]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const addEntity = async (watchlistId: string) => {
    const ticker = (newTicker[watchlistId] ?? '').trim().toUpperCase();
    if (!ticker) return;
    try {
      await api.post(`/v3/portfolios/watchlists/${watchlistId}/entities`, { ticker });
      setNewTicker((prev) => ({ ...prev, [watchlistId]: '' }));
      fetchWatchlists();
    } catch {
      // no-op
    }
  };

  const removeEntity = async (watchlistId: string, ticker: string) => {
    try {
      await api.post(`/v3/portfolios/watchlists/${watchlistId}/entities/remove`, { ticker });
      fetchWatchlists();
    } catch {
      // no-op
    }
  };

  const createWatchlist = async () => {
    const name = newListName.trim();
    if (!name) return;
    setCreatingList(true);
    try {
      await api.post('/v3/portfolios/watchlists', { name });
      setNewListName('');
      fetchWatchlists();
    } catch {
      // no-op
    } finally {
      setCreatingList(false);
    }
  };

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  };

  const inputStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-primary)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    padding: '3px 8px',
    height: '24px',
    outline: 'none',
  };

  if (loading) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        Loading watchlists...
      </div>
    );
  }

  if (error) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        {error}
      </div>
    );
  }

  return (
    <div className="animate-in" style={rootStyle}>
      {watchlists.map((wl) => {
        const isExpanded = expandedIds.has(wl.id);
        return (
          <div
            key={wl.id}
            style={{
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden',
            }}
          >
            {/* List header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: '6px 10px',
                background: 'var(--color-surface-raised)',
                cursor: 'pointer',
                userSelect: 'none',
              }}
              onClick={() => toggleExpand(wl.id)}
            >
              <span
                style={{
                  display: 'inline-block',
                  transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 0.15s',
                  fontSize: '9px',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                &#9654;
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  color: 'var(--color-text-primary)',
                  flex: 1,
                }}
              >
                {wl.name}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                {wl.entities.length}
              </span>
            </div>

            {/* Entity list */}
            {isExpanded && (
              <div>
                {wl.entities.map((entity) => (
                  <div
                    key={entity.ticker}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '70px 1fr 80px 70px 70px 24px',
                      gap: 'var(--space-2)',
                      alignItems: 'center',
                      padding: '5px 10px',
                      borderTop: '1px solid var(--color-surface-border)',
                      cursor: onSelectSecurity ? 'pointer' : 'default',
                      transition: 'background 0.1s',
                    }}
                    onClick={() => onSelectSecurity?.(entity.ticker)}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLDivElement).style.background = 'transparent';
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontWeight: 700,
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-accent-primary)',
                      }}
                    >
                      {entity.ticker}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-secondary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {entity.name}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontVariantNumeric: 'tabular-nums',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-primary)',
                        textAlign: 'right',
                      }}
                    >
                      ${entity.price.toFixed(2)}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontVariantNumeric: 'tabular-nums',
                        fontSize: 'var(--text-xs)',
                        color: entity.dayChange >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)',
                        textAlign: 'right',
                      }}
                    >
                      {entity.dayChange >= 0 ? '+' : ''}{entity.dayChange.toFixed(2)}%
                    </span>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      {entity.qualityScore != null && (
                        <QualityScoreCell score={entity.qualityScore} max={100} />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEntity(wl.id, entity.ticker);
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-text-tertiary)',
                        cursor: 'pointer',
                        fontSize: '12px',
                        padding: '0',
                        lineHeight: 1,
                      }}
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                ))}

                {/* Add entity */}
                <div
                  style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    alignItems: 'center',
                    padding: '6px 10px',
                    borderTop: '1px solid var(--color-surface-border)',
                    background: 'var(--color-surface-raised)',
                  }}
                >
                  <input
                    style={{ ...inputStyle, width: '80px', textTransform: 'uppercase' }}
                    placeholder="TICKER"
                    value={newTicker[wl.id] ?? ''}
                    onChange={(e) =>
                      setNewTicker((prev) => ({ ...prev, [wl.id]: e.target.value }))
                    }
                    onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === 'Enter') addEntity(wl.id);
                    }}
                    maxLength={10}
                  />
                  <button
                    type="button"
                    onClick={() => addEntity(wl.id)}
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '3px 10px',
                      height: '24px',
                      background: 'transparent',
                      color: 'var(--color-accent-primary)',
                      border: '1px solid var(--color-accent-primary)',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    + Add
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Create new watchlist */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: 'var(--space-2)',
          borderTop: '1px solid var(--color-surface-border)',
        }}
      >
        <input
          style={{ ...inputStyle, flex: 1 }}
          placeholder="New watchlist name..."
          value={newListName}
          onChange={(e) => setNewListName(e.target.value)}
          onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
            if (e.key === 'Enter') createWatchlist();
          }}
        />
        <button
          type="button"
          onClick={createWatchlist}
          disabled={creatingList || !newListName.trim()}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            padding: '3px 12px',
            height: '24px',
            background: 'var(--color-accent-primary)',
            color: 'var(--color-surface-void)',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: creatingList || !newListName.trim() ? 'not-allowed' : 'pointer',
            opacity: !newListName.trim() ? 0.5 : 1,
          }}
        >
          Create
        </button>
      </div>
    </div>
  );
}

export default WatchlistPanel;
