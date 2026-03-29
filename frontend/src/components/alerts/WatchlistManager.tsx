import { useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface WatchlistEntity {
  id: string;
  ticker: string;
  name: string;
  alertsEnabled: {
    price: boolean;
    filing: boolean;
    earnings: boolean;
    score: boolean;
  };
}

export interface WatchlistManagerProps {
  entities: WatchlistEntity[];
  onAdd: () => void;
  onRemove: (id: string) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
  onToggleAlert?: (id: string, alertType: keyof WatchlistEntity['alertsEnabled']) => void;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ALERT_TYPES: { key: keyof WatchlistEntity['alertsEnabled']; label: string }[] = [
  { key: 'price', label: 'Price' },
  { key: 'filing', label: 'Filing' },
  { key: 'earnings', label: 'Earnings' },
  { key: 'score', label: 'Score' },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function WatchlistManager({
  entities,
  onAdd,
  onRemove,
  onReorder,
  onToggleAlert,
  className,
}: WatchlistManagerProps) {
  const handleMoveUp = useCallback(
    (idx: number) => {
      if (idx > 0) onReorder(idx, idx - 1);
    },
    [onReorder],
  );

  const handleMoveDown = useCallback(
    (idx: number) => {
      if (idx < entities.length - 1) onReorder(idx, idx + 1);
    },
    [onReorder, entities.length],
  );

  return (
    <div
      className={clsx('flex flex-col gap-3', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '16px',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Watchlist
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          {entities.length} entities
        </span>
      </div>

      {/* Column labels */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr repeat(4, 48px) 60px',
          gap: 4,
          padding: '0 8px',
        }}
      >
        <span style={colHeaderStyle}>Entity</span>
        {ALERT_TYPES.map((at) => (
          <span key={at.key} style={{ ...colHeaderStyle, textAlign: 'center' }}>
            {at.label}
          </span>
        ))}
        <span style={colHeaderStyle} />
      </div>

      {/* Entity rows */}
      {entities.map((entity, idx) => (
        <div
          key={entity.id}
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr repeat(4, 48px) 60px',
            gap: 4,
            alignItems: 'center',
            padding: '6px 8px',
            background: 'var(--color-surface-raised)',
            borderRadius: 4,
            border: '1px solid var(--color-surface-border)',
          }}
        >
          {/* Entity info */}
          <div className="flex flex-col" style={{ minWidth: 0 }}>
            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                color: 'var(--color-accent-primary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {entity.ticker}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {entity.name}
            </span>
          </div>

          {/* Alert toggles */}
          {ALERT_TYPES.map((at) => {
            const enabled = entity.alertsEnabled[at.key];
            return (
              <button
                key={at.key}
                type="button"
                onClick={() => onToggleAlert?.(entity.id, at.key)}
                style={{
                  width: 32,
                  height: 18,
                  borderRadius: 9,
                  background: enabled
                    ? 'var(--color-signal-positive)'
                    : 'var(--color-surface-overlay, rgba(255,255,255,0.06))',
                  border: `1px solid ${enabled ? 'var(--color-signal-positive)' : 'var(--color-surface-border)'}`,
                  position: 'relative',
                  cursor: 'pointer',
                  justifySelf: 'center',
                  padding: 0,
                  transition: 'background 0.15s',
                }}
                title={`${at.label} alerts ${enabled ? 'enabled' : 'disabled'}`}
                aria-label={`Toggle ${at.label} alerts for ${entity.ticker}`}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: 2,
                    left: enabled ? 16 : 2,
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: 'var(--color-text-primary)',
                    transition: 'left 0.15s',
                  }}
                />
              </button>
            );
          })}

          {/* Actions */}
          <div className="flex items-center gap-1 justify-end">
            <button
              type="button"
              onClick={() => handleMoveUp(idx)}
              disabled={idx === 0}
              style={{
                ...navBtnStyle,
                opacity: idx === 0 ? 0.3 : 1,
              }}
              title="Move up"
              aria-label={`Move ${entity.ticker} up`}
            >
              {'\u25B2'}
            </button>
            <button
              type="button"
              onClick={() => handleMoveDown(idx)}
              disabled={idx === entities.length - 1}
              style={{
                ...navBtnStyle,
                opacity: idx === entities.length - 1 ? 0.3 : 1,
              }}
              title="Move down"
              aria-label={`Move ${entity.ticker} down`}
            >
              {'\u25BC'}
            </button>
            <button
              type="button"
              onClick={() => onRemove(entity.id)}
              style={{
                ...navBtnStyle,
                color: 'var(--color-signal-negative)',
              }}
              title="Remove"
              aria-label={`Remove ${entity.ticker}`}
            >
              {'\u2715'}
            </button>
          </div>
        </div>
      ))}

      {/* Add button */}
      <button
        type="button"
        onClick={onAdd}
        style={{
          alignSelf: 'flex-start',
          background: 'var(--color-surface-raised)',
          color: 'var(--color-accent-primary)',
          border: '1px solid var(--color-surface-border)',
          borderRadius: 4,
          padding: '6px 14px',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
          cursor: 'pointer',
          letterSpacing: '0.02em',
          transition: 'background var(--transition-fast, 0.1s)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--color-surface-overlay)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'var(--color-surface-raised)';
        }}
      >
        + Add Entity
      </button>

      {entities.length === 0 && (
        <div
          style={{
            padding: '16px 0',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          No entities in watchlist. Add one to get started.
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const colHeaderStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: '9px',
  fontWeight: 500,
  color: 'var(--color-text-tertiary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const navBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--color-text-tertiary)',
  cursor: 'pointer',
  fontSize: 10,
  lineHeight: 1,
  padding: '2px 3px',
};
