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
  CRITICAL: 'var(--signal-negative)',
  HIGH: 'var(--signal-warning)',
  MEDIUM: 'var(--signal-highlight)',
  LOW: 'var(--text-tertiary)',
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
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-4)',
      }}
    >
      {/* Header */}
      {entityName && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: 'var(--space-3)',
          }}
        >
          Alert Timeline &mdash;{' '}
          <span style={{ fontFamily: 'var(--font-data)', color: 'var(--accent-primary)', fontVariantNumeric: 'tabular-nums' }}>
            {entityName}
          </span>
        </span>
      )}

      {/* Timeline */}
      {grouped.map((group) => (
        <div key={group.date} style={{ marginBottom: 'var(--space-4)' }}>
          {/* Date header with horizontal rule */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              marginBottom: 'var(--space-2)',
              paddingLeft: 'var(--space-5)',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                whiteSpace: 'nowrap',
              }}
            >
              {formatDate(group.items[0]?.createdAt ?? group.date)}
            </span>
            <div
              style={{
                flex: 1,
                height: 1,
                background: 'var(--surface-border)',
              }}
            />
          </div>

          {/* Timeline items */}
          {group.items.map((alert, idx) => {
            const isLast = idx === group.items.length - 1;
            const sevColor =
              SEVERITY_COLORS[alert.severity] ?? 'var(--text-tertiary)';
            const isExpanded = expandedId === alert.id;

            return (
              <div
                key={alert.id}
                style={{ display: 'flex', gap: 'var(--space-3)', position: 'relative' }}
              >
                {/* Timeline rail */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    width: 12,
                    flexShrink: 0,
                  }}
                >
                  {/* Dot — 10px, severity-colored */}
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: sevColor,
                      flexShrink: 0,
                      marginTop: 'var(--space-1)',
                      boxShadow: `0 0 6px ${sevColor}`,
                    }}
                  />
                  {/* Line — 2px wide, surface-border-strong */}
                  {!isLast && (
                    <div
                      style={{
                        width: 2,
                        flex: 1,
                        background: 'var(--surface-border-strong)',
                        minHeight: 'var(--space-5)',
                      }}
                    />
                  )}
                </div>

                {/* Content */}
                <div
                  style={{
                    flex: 1,
                    paddingBottom: isLast ? 0 : 'var(--space-3)',
                    minWidth: 0,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(alert.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 'var(--space-2)',
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
                        color: 'var(--text-tertiary)',
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
                        color: 'var(--text-primary)',
                        fontWeight: 500,
                        lineHeight: 1.3,
                      }}
                    >
                      {alert.title}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-data)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: 500,
                        fontVariantNumeric: 'tabular-nums',
                        color: sevColor,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        flexShrink: 0,
                      }}
                    >
                      {alert.severity}
                    </span>
                  </button>

                  {/* Expand animation: slide down 200ms ease */}
                  <div
                    style={{
                      overflow: 'hidden',
                      maxHeight: isExpanded ? '200px' : '0px',
                      transition: 'max-height 200ms ease-out',
                    }}
                  >
                    <p
                      style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.5,
                        margin: 'var(--space-1) 0 0 0',
                        paddingLeft: 0,
                      }}
                    >
                      {alert.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {alerts.length === 0 && (
        <div
          style={{
            padding: 'var(--space-6) 0',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-tertiary)',
          }}
        >
          No alerts in timeline
        </div>
      )}
    </div>
  );
}
