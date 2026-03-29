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
  CRITICAL: 'var(--color-signal-negative)',
  HIGH: 'var(--color-signal-warning)',
  MEDIUM: 'var(--color-signal-neutral)',
  LOW: 'var(--color-text-tertiary)',
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
      className={clsx('flex flex-col', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        overflow: 'hidden',
      }}
    >
      {grouped.map(([severity, items]) => {
        const sevColor =
          SEVERITY_COLORS[severity] ?? 'var(--color-text-tertiary)';

        return (
          <div key={severity}>
            {/* Group header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 12px',
                background: 'var(--color-surface-raised)',
                borderBottom: '1px solid var(--color-surface-border)',
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
                  color: 'var(--color-text-tertiary)',
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
            padding: '24px 16px',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          No alerts
        </div>
      )}
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
        borderBottom: '1px solid var(--color-surface-border)',
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
          gap: 8,
          padding: '8px 12px',
          background: isExpanded ? 'var(--color-surface-raised)' : 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {/* Unread dot */}
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: alert.isRead ? 'transparent' : color,
            flexShrink: 0,
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
            color: 'var(--color-text-primary)',
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
              color: 'var(--color-accent-primary)',
              padding: '1px 6px',
              background: 'rgba(59, 130, 246, 0.10)',
              borderRadius: 3,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {alert.entityTicker}
          </span>
        )}

        {/* Time */}
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            whiteSpace: 'nowrap',
            flexShrink: 0,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {timeAgo(alert.createdAt)}
        </span>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div
          style={{
            padding: '8px 12px 12px 38px',
            background: 'var(--color-surface-raised)',
          }}
        >
          <p
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-secondary)',
              lineHeight: 1.5,
              margin: '0 0 10px 0',
            }}
          >
            {alert.description}
          </p>
          <div className="flex gap-2">
            <ActionButton
              label="Acknowledge"
              color="var(--color-accent-primary)"
              onClick={() => onAcknowledge(alert.id)}
            />
            <ActionButton
              label="Dismiss"
              color="var(--color-text-tertiary)"
              onClick={() => onDismiss(alert.id)}
            />
          </div>
        </div>
      )}
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
        background: 'var(--color-surface-base)',
        border: `1px solid ${color}`,
        borderRadius: 4,
        padding: '4px 12px',
        cursor: 'pointer',
        letterSpacing: '0.02em',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--color-surface-overlay, rgba(255,255,255,0.06))';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--color-surface-base)';
      }}
    >
      {label}
    </button>
  );
}
