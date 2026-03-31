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

const TIME_BADGE_COLOR: Record<string, string> = {
  BMO: 'var(--chart-1)',
  AMC: 'var(--chart-3)',
  DMH: 'var(--text-tertiary)',
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
      {/* Header */}
      <div
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderBottom: '1px solid var(--surface-border)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--text-primary)',
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
            {/* Date group header — sticky, font-ui text-xs text-secondary */}
            <div
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 1,
                padding: 'var(--space-1) var(--space-3)',
                background: 'var(--surface-raised)',
                borderBottom: '1px solid var(--surface-border)',
                borderLeft: today ? '3px solid var(--accent-primary)' : '3px solid transparent',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: today
                    ? 'var(--accent-primary)'
                    : 'var(--text-secondary)',
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
                    fontSize: 'var(--text-xs)',
                    fontWeight: 500,
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--accent-primary)',
                    padding: '1px var(--space-1)',
                    background: 'color-mix(in srgb, var(--accent-primary) 15%, transparent)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  TODAY
                </span>
              )}
            </div>

            {/* Event rows */}
            {group.items.map((ev) => {
              const isWatchlisted = watchSet.has(ev.ticker.toUpperCase());
              const timeBadgeColor = TIME_BADGE_COLOR[ev.time] ?? 'var(--text-tertiary)';

              return (
                <div
                  key={ev.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-1) var(--space-3)',
                    borderBottom: '1px solid var(--surface-border)',
                    background: isWatchlisted
                      ? 'color-mix(in srgb, var(--signal-highlight) 10%, transparent)'
                      : 'transparent',
                    transition: 'background var(--transition-fast)',
                  }}
                >
                  {/* Watchlist indicator */}
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: isWatchlisted
                        ? 'var(--accent-primary)'
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
                      fontVariantNumeric: 'tabular-nums',
                      color: isWatchlisted
                        ? 'var(--accent-primary)'
                        : 'var(--text-primary)',
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
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {ev.companyName}
                  </span>

                  {/* Expected EPS — font-data tabular-nums */}
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--text-primary)',
                      fontVariantNumeric: 'tabular-nums',
                      minWidth: 56,
                      textAlign: 'right',
                      flexShrink: 0,
                    }}
                  >
                    {ev.expectedEps != null ? `$${ev.expectedEps.toFixed(2)}` : '\u2014'}
                  </span>

                  {/* Time badge — BMO=chart-1, AMC=chart-3 */}
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      fontVariantNumeric: 'tabular-nums',
                      color: timeBadgeColor,
                      background: `color-mix(in srgb, ${timeBadgeColor} 15%, transparent)`,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '1px var(--space-1)',
                      borderRadius: 'var(--radius-sm)',
                      minWidth: 28,
                      textAlign: 'center',
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
            padding: 'var(--space-6) var(--space-4)',
            textAlign: 'center',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-tertiary)',
          }}
        >
          No upcoming earnings events
        </div>
      )}
    </div>
  );
}
