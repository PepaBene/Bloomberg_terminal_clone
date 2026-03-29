import { useState, useCallback, useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface TimelineAlert {
  id: string;
  title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  createdAt: string;
}

export interface AlertTimelineProps {
  alerts: TimelineAlert[];
  entityName?: string;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'var(--color-signal-negative)',
  HIGH: 'var(--color-signal-warning)',
  MEDIUM: 'var(--color-signal-neutral)',
  LOW: 'var(--color-text-tertiary)',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function dateKey(dateStr: string): string {
  return new Date(dateStr).toISOString().slice(0, 10);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AlertTimeline({
  alerts,
  entityName,
  className,
}: AlertTimelineProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  /** Group alerts by date */
  const grouped = useMemo(() => {
    const sorted = [...alerts].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
    const groups: { date: string; items: TimelineAlert[] }[] = [];
    let currentDate = '';
    for (const alert of sorted) {
      const dk = dateKey(alert.createdAt);
      if (dk !== currentDate) {
        currentDate = dk;
        groups.push({ date: dk, items: [] });
      }
      groups[groups.length - 1]?.items.push(alert);
    }
    return groups;
  }, [alerts]);

  return (
    <div
      className={clsx('flex flex-col', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '16px',
      }}
    >
      {/* Header */}
      {entityName && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: 12,
          }}
        >
          Alert Timeline — {entityName}
        </span>
      )}

      {/* Timeline */}
      {grouped.map((group) => (
        <div key={group.date} style={{ marginBottom: 16 }}>
          {/* Date header */}
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: 8,
              paddingLeft: 20,
            }}
          >
            {formatDate(group.items[0]?.createdAt ?? group.date)}
          </div>

          {/* Timeline items */}
          {group.items.map((alert, idx) => {
            const isLast = idx === group.items.length - 1;
            const sevColor =
              SEVERITY_COLORS[alert.severity] ?? 'var(--color-text-tertiary)';
            const isExpanded = expandedId === alert.id;

            return (
              <div
                key={alert.id}
                style={{ display: 'flex', gap: 12, position: 'relative' }}
              >
                {/* Timeline rail */}
                <div
                  className="flex flex-col items-center"
                  style={{ width: 12, flexShrink: 0 }}
                >
                  {/* Dot */}
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: sevColor,
                      flexShrink: 0,
                      marginTop: 4,
                      boxShadow: `0 0 6px ${sevColor}`,
                    }}
                  />
                  {/* Line */}
                  {!isLast && (
                    <div
                      style={{
                        width: 2,
                        flex: 1,
                        background: 'var(--color-surface-border)',
                        minHeight: 20,
                      }}
                    />
                  )}
                </div>

                {/* Content */}
                <div
                  style={{
                    flex: 1,
                    paddingBottom: isLast ? 0 : 12,
                    minWidth: 0,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(alert.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 8,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-tertiary)',
                        fontVariantNumeric: 'tabular-nums',
                        flexShrink: 0,
                      }}
                    >
                      {formatTime(alert.createdAt)}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--color-text-primary)',
                        fontWeight: 500,
                        lineHeight: 1.3,
                      }}
                    >
                      {alert.title}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontSize: '9px',
                        fontWeight: 500,
                        color: sevColor,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        flexShrink: 0,
                      }}
                    >
                      {alert.severity}
                    </span>
                  </button>

                  {isExpanded && (
                    <p
                      style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.5,
                        margin: '6px 0 0 0',
                        paddingLeft: 0,
                      }}
                    >
                      {alert.description}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {alerts.length === 0 && (
        <div
          style={{
            padding: '24px 0',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          No alerts in timeline
        </div>
      )}
    </div>
  );
}
