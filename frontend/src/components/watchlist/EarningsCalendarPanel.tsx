import { useState, useEffect, useMemo } from 'react';
import type { CSSProperties } from 'react';
import { api } from '@/api/client';
import { SignalBadge } from '@/components/ui/SignalBadge';

export interface EarningsCalendarPanelProps {
  tickers: string[];
  daysAhead?: number;
}

interface EarningsEvent {
  ticker: string;
  company: string;
  date: string;
  time: 'BMO' | 'AMC' | 'TBD';
  epsEstimate?: number;
  epsActual?: number;
}

function daysBetween(dateStr: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function rowColorStyle(daysAway: number): CSSProperties {
  if (daysAway === 0) return { borderLeft: '3px solid var(--color-accent-primary)' };
  if (daysAway <= 7) return { borderLeft: '3px solid var(--color-signal-neutral)' };
  return { borderLeft: '3px solid transparent', opacity: 0.75 };
}


export function EarningsCalendarPanel({
  tickers,
  daysAhead = 30,
}: EarningsCalendarPanelProps) {
  const [events, setEvents] = useState<EarningsEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tickers.length) return;
    setLoading(true);
    api
      .get(`/v3/research/earnings-calendar?tickers=${tickers.join(',')}&days=${daysAhead}`)
      .then((data: unknown) => {
        setEvents(Array.isArray(data) ? (data as EarningsEvent[]) : []);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [tickers, daysAhead]);

  const sorted = useMemo(
    () => [...events].sort((a, b) => a.date.localeCompare(b.date)),
    [events],
  );

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  };

  const headerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '70px 1fr 90px 80px 70px 70px',
    gap: 'var(--space-2)',
    padding: '4px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  if (loading) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        Loading earnings calendar...
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

  if (!sorted.length) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        No earnings events in the next {daysAhead} days.
      </div>
    );
  }

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={headerStyle}>
        <span>Ticker</span>
        <span>Company</span>
        <span>Date</span>
        <span>Time</span>
        <span style={{ textAlign: 'right' }}>Est EPS</span>
        <span style={{ textAlign: 'right' }}>Actual</span>
      </div>

      {sorted.map((ev, i) => {
        const days = daysBetween(ev.date);
        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '70px 1fr 90px 80px 70px 70px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '6px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          transition: 'background 0.1s',
          ...rowColorStyle(days),
        };

        let daysLabel = days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : `${days}d`;

        return (
          <div
            key={i}
            style={rowStyle}
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
              {ev.ticker}
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
              {ev.company}
            </span>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  color: days === 0 ? 'var(--color-accent-primary)' : 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {ev.date}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: '10px',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                {daysLabel}
              </span>
            </div>

            <SignalBadge
              label={ev.time}
              variant={ev.time === 'BMO' ? 'neutral' : ev.time === 'AMC' ? 'highlight' : 'neutral'}
            />

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                textAlign: 'right',
              }}
            >
              {ev.epsEstimate != null ? `$${ev.epsEstimate.toFixed(2)}` : '--'}
            </span>

            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
                fontSize: 'var(--text-xs)',
                color: ev.epsActual != null && ev.epsEstimate != null
                  ? ev.epsActual >= ev.epsEstimate
                    ? 'var(--color-signal-positive)'
                    : 'var(--color-signal-negative)'
                  : 'var(--color-text-tertiary)',
                textAlign: 'right',
              }}
            >
              {ev.epsActual != null ? `$${ev.epsActual.toFixed(2)}` : '--'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default EarningsCalendarPanel;
