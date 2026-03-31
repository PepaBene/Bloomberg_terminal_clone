import { useState, useCallback, useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  entityTicker?: string;
  createdAt: string;
  isRead: boolean;
}

export interface AlertInboxProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
  onDismiss: (id: string) => void;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'var(--signal-negative)',
  HIGH: 'var(--signal-warning)',
  MEDIUM: 'var(--signal-highlight)',
  LOW: 'var(--text-tertiary)',
};

const SEVERITY_ICONS: Record<string, string> = {
  CRITICAL: '\u26D4',
  HIGH: '\u26A0',
  MEDIUM: '\u2139',
  LOW: '\u25CB',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AlertInbox({
  alerts,
  onAcknowledge,
  onDismiss,
  className,
}: AlertInboxProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  /** Group alerts by severity */
  const grouped = useMemo(() => {
    const groups = new Map<string, Alert[]>();
    const sorted = [...alerts].sort(
      (a, b) =>
        (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4),
    );
    for (const alert of sorted) {
      const existing = groups.get(alert.severity);
      if (existing) {
        existing.push(alert);
      } else {
        groups.set(alert.severity, [alert]);
      }
    }
    return Array.from(groups.entries());
  }, [alerts]);

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        overflow: 'hidden',
      }}
    >
      {grouped.map(([severity, items]) => {
        const sevColor =
          SEVERITY_COLORS[severity] ?? 'var(--text-tertiary)';

        return (
          <div key={severity}>
            {/* Group header with 3px left border */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-1) var(--space-3)',
                background: 'var(--surface-raised)',
                borderBottom: '1px solid var(--surface-border)',
                borderLeft: `3px solid ${sevColor}`,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: sevColor,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                {severity}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  fontVariantNumeric: 'tabular-nums',
                  color: 'var(--text-tertiary)',
                }}
              >
                {items.length}
              </span>
            </div>

            {/* Alert rows */}
            {items.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                color={sevColor}
                icon={SEVERITY_ICONS[severity] ?? '\u25CB'}
                isExpanded={expandedId === alert.id}
                onToggle={toggleExpand}
                onAcknowledge={onAcknowledge}
                onDismiss={onDismiss}
              />
            ))}
          </div>
        );
      })}

      {alerts.length === 0 && (
        <div
          style={{
            padding: 'var(--space-6) var(--space-4)',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-tertiary)',
          }}
        >
          No alerts
        </div>
      )}

      {/* Unread dot pulse animation */}
      <style>{`
        @keyframes unreadPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Alert row                                                          */
/* ------------------------------------------------------------------ */

function AlertRow({
  alert,
  color,
  icon,
  isExpanded,
  onToggle,
  onAcknowledge,
  onDismiss,
}: {
  alert: Alert;
  color: string;
  icon: string;
  isExpanded: boolean;
  onToggle: (id: string) => void;
  onAcknowledge: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      style={{
        borderBottom: '1px solid var(--surface-border)',
      }}
    >
      {/* Summary row */}
      <button
        type="button"
        onClick={() => onToggle(alert.id)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
          padding: 'var(--space-2) var(--space-3)',
          background: isExpanded ? 'var(--surface-raised)' : 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={(e) => {
          if (!isExpanded) e.currentTarget.style.background = 'var(--surface-overlay)';
        }}
        onMouseLeave={(e) => {
          if (!isExpanded) e.currentTarget.style.background = 'transparent';
        }}
      >
        {/* Unread dot — 6px, accent-primary, subtle pulse */}
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: alert.isRead ? 'transparent' : 'var(--accent-primary)',
            flexShrink: 0,
            animation: !alert.isRead ? 'unreadPulse 2s ease-in-out infinite' : undefined,
          }}
        />

        {/* Icon */}
        <span
          style={{
            fontSize: 14,
            lineHeight: 1,
            color,
            flexShrink: 0,
          }}
        >
          {icon}
        </span>

        {/* Title */}
        <span
          style={{
            flex: 1,
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)',
            fontWeight: alert.isRead ? 400 : 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {alert.title}
        </span>

        {/* Ticker */}
        {alert.entityTicker && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--accent-primary)',
              padding: '1px var(--space-1)',
              background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
              borderRadius: 'var(--radius-sm)',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {alert.entityTicker}
          </span>
        )}

        {/* Time ago */}
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-tertiary)',
            whiteSpace: 'nowrap',
            flexShrink: 0,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {timeAgo(alert.createdAt)}
        </span>
      </button>

      {/* Expanded detail — smooth height transition */}
      <div
        style={{
          overflow: 'hidden',
          maxHeight: isExpanded ? '400px' : '0px',
          transition: 'max-height 200ms ease-out',
        }}
      >
        <div
          style={{
            padding: 'var(--space-2) var(--space-3) var(--space-3) 38px',
            background: 'var(--surface-raised)',
          }}
        >
          <p
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              margin: '0 0 var(--space-2) 0',
            }}
          >
            {alert.description}
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <ActionButton
              label="Acknowledge"
              color="var(--accent-primary)"
              onClick={() => onAcknowledge(alert.id)}
            />
            <ActionButton
              label="Dismiss"
              color="var(--text-tertiary)"
              onClick={() => onDismiss(alert.id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Action button                                                      */
/* ------------------------------------------------------------------ */

function ActionButton({
  label,
  color,
  onClick,
}: {
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-xs)',
        fontWeight: 500,
        color,
        background: 'var(--surface-base)',
        border: `1px solid ${color}`,
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-1) var(--space-3)',
        cursor: 'pointer',
        letterSpacing: '0.02em',
        transition: 'background var(--transition-fast)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--surface-overlay)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--surface-base)';
      }}
    >
      {label}
    </button>
  );
}
