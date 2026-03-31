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
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-4)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--text-primary)',
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
            fontVariantNumeric: 'tabular-nums',
            color: 'var(--text-tertiary)',
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
          gap: 'var(--space-1)',
          padding: '0 var(--space-2)',
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
            gap: 'var(--space-1)',
            alignItems: 'center',
            padding: 'var(--space-1) var(--space-2)',
            background: 'var(--surface-raised)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--surface-border)',
            transition: 'background var(--transition-fast)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--surface-overlay)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--surface-raised)';
          }}
        >
          {/* Entity info */}
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                fontVariantNumeric: 'tabular-nums',
                color: 'var(--accent-primary)',
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
                color: 'var(--text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {entity.name}
            </span>
          </div>

          {/* Alert toggle switches — 24px wide, accent-primary when on */}
          {ALERT_TYPES.map((at) => {
            const enabled = entity.alertsEnabled[at.key];
            return (
              <button
                key={at.key}
                type="button"
                onClick={() => onToggleAlert?.(entity.id, at.key)}
                style={{
                  width: 24,
                  height: 14,
                  borderRadius: 7,
                  background: enabled
                    ? 'var(--accent-primary)'
                    : 'var(--surface-border-strong)',
                  border: 'none',
                  position: 'relative',
                  cursor: 'pointer',
                  justifySelf: 'center',
                  padding: 0,
                  transition: 'background var(--transition-fast)',
                }}
                title={`${at.label} alerts ${enabled ? 'enabled' : 'disabled'}`}
                aria-label={`Toggle ${at.label} alerts for ${entity.ticker}`}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: 2,
                    left: enabled ? 12 : 2,
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: 'var(--text-primary)',
                    transition: 'left var(--transition-fast)',
                  }}
                />
              </button>
            );
          })}

          {/* Actions — subtle reorder + remove */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', justifyContent: 'flex-end' }}>
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
                color: 'var(--text-tertiary)',
                transition: 'color var(--transition-fast)',
              }}
              title="Remove"
              aria-label={`Remove ${entity.ticker}`}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--signal-negative)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-tertiary)';
              }}
            >
              {'\u2715'}
            </button>
          </div>
        </div>
      ))}

      {/* Add button — accent-primary, full width */}
      <button
        type="button"
        onClick={onAdd}
        style={{
          width: '100%',
          background: 'var(--surface-raised)',
          color: 'var(--accent-primary)',
          border: '1px solid var(--surface-border)',
          borderRadius: 'var(--radius-sm)',
          padding: 'var(--space-2) var(--space-4)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
          cursor: 'pointer',
          letterSpacing: '0.02em',
          transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--surface-overlay)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'var(--surface-raised)';
        }}
      >
        + Add Entity
      </button>

      {entities.length === 0 && (
        <div
          style={{
            padding: 'var(--space-4) 0',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-tertiary)',
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
  fontSize: 'var(--text-xs)',
  fontWeight: 500,
  color: 'var(--text-tertiary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const navBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
  fontSize: 10,
  lineHeight: 1,
  padding: '2px var(--space-1)',
};
