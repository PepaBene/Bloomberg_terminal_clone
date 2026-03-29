import { useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface EarningsEvent {
  id: string;
  date: string;
  ticker: string;
  companyName: string;
  expectedEps: number | null;
  time: 'BMO' | 'AMC' | 'DMH';
}

export interface EarningsCalendarWidgetProps {
  events: EarningsEvent[];
  watchlistTickers?: string[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const TIME_LABELS: Record<string, string> = {
  BMO: 'Before Open',
  AMC: 'After Close',
  DMH: 'During Hours',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function isToday(dateStr: string): boolean {
  const d = new Date(dateStr);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function dateKey(dateStr: string): string {
  return new Date(dateStr).toISOString().slice(0, 10);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function EarningsCalendarWidget({
  events,
  watchlistTickers,
  className,
}: EarningsCalendarWidgetProps) {
  const watchSet = useMemo(
    () => new Set(watchlistTickers?.map((t) => t.toUpperCase()) ?? []),
    [watchlistTickers],
  );

  /** Group events by date */
  const grouped = useMemo(() => {
    const sorted = [...events].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );
    const groups: { date: string; items: EarningsEvent[] }[] = [];
    let currentDate = '';
    for (const ev of sorted) {
      const dk = dateKey(ev.date);
      if (dk !== currentDate) {
        currentDate = dk;
        groups.push({ date: dk, items: [] });
      }
      groups[groups.length - 1]?.items.push(ev);
    }
    return groups;
  }, [events]);

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
      {/* Header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid var(--color-surface-border)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Earnings Calendar
      </div>

      {grouped.map((group) => {
        const today = group.items[0] ? isToday(group.items[0].date) : false;

        return (
          <div key={group.date}>
            {/* Date header */}
            <div
              style={{
                padding: '6px 12px',
                background: today
                  ? 'rgba(59, 130, 246, 0.08)'
                  : 'var(--color-surface-raised)',
                borderBottom: '1px solid var(--color-surface-border)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: today
                    ? 'var(--color-accent-primary)'
                    : 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                {formatDateShort(group.items[0]?.date ?? group.date)}
              </span>
              {today && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: '9px',
                    fontWeight: 500,
                    color: 'var(--color-accent-primary)',
                    padding: '1px 6px',
                    border: '1px solid var(--color-accent-primary)',
                    borderRadius: '9999px',
                  }}
                >
                  TODAY
                </span>
              )}
            </div>

            {/* Event rows */}
            {group.items.map((ev) => {
              const isWatchlisted = watchSet.has(ev.ticker.toUpperCase());

              return (
                <div
                  key={ev.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 12px',
                    borderBottom: '1px solid var(--color-surface-border)',
                    background: isWatchlisted
                      ? 'rgba(59, 130, 246, 0.04)'
                      : 'transparent',
                  }}
                >
                  {/* Watchlist indicator */}
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: isWatchlisted
                        ? 'var(--color-accent-primary)'
                        : 'transparent',
                      flexShrink: 0,
                    }}
                  />

                  {/* Ticker */}
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-sm)',
                      fontWeight: 600,
                      color: isWatchlisted
                        ? 'var(--color-accent-primary)'
                        : 'var(--color-text-primary)',
                      minWidth: 60,
                      flexShrink: 0,
                    }}
                  >
                    {ev.ticker}
                  </span>

                  {/* Company name */}
                  <span
                    style={{
                      flex: 1,
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--color-text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {ev.companyName}
                  </span>

                  {/* Expected EPS */}
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-text-primary)',
                      fontVariantNumeric: 'tabular-nums',
                      minWidth: 56,
                      textAlign: 'right',
                      flexShrink: 0,
                    }}
                  >
                    {ev.expectedEps != null ? `$${ev.expectedEps.toFixed(2)}` : '\u2014'}
                  </span>

                  {/* Time badge */}
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: '9px',
                      fontWeight: 500,
                      color: 'var(--color-text-tertiary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      minWidth: 28,
                      textAlign: 'right',
                      flexShrink: 0,
                    }}
                    title={TIME_LABELS[ev.time] ?? ev.time}
                  >
                    {ev.time}
                  </span>
                </div>
              );
            })}
          </div>
        );
      })}

      {events.length === 0 && (
        <div
          style={{
            padding: '24px 16px',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          No upcoming earnings events
        </div>
      )}
    </div>
  );
}
