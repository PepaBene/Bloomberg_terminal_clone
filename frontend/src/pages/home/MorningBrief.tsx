// ---------------------------------------------------------------------------
// Morning Brief -- Landing Page
//
// Wired to real backend endpoints where they exist:
//   - Top Movers      -> GET /v1/analytics/movers   (market_movers.py)
//   - Alerts          -> GET /v3/alerts             (alerts.py)
//   - Economic Cal.   -> GET /v3/news/calendar/economic (economic_calendar.py)
//
// The Market Overview (index quotes), Sector Performance, and the S&P intraday
// chart have NO backend producer today, so they render an honest empty state
// instead of fabricated numbers. (Previously every panel silently fell back to
// hardcoded mock data and the chart was Math.random() noise — DATA_WIRING_AUDIT
// §8.1/§8.3.)
// ---------------------------------------------------------------------------

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { EmptyState } from '@/components/feedback';
import { useSecurityStore } from '@/stores/securityContext';
import { useNavigationStore } from '@/stores/navigationHistory';

// --- Helpers ----------------------------------------------------------------

function signalColor(value: number): string {
  return value >= 0
    ? 'var(--color-signal-positive)'
    : 'var(--color-signal-negative)';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatPrice(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function severityColor(s: AlertItem['severity']): string {
  switch (s) {
    case 'high':   return 'var(--color-signal-negative)';
    case 'medium': return 'var(--color-signal-warning)';
    default:       return 'var(--color-signal-neutral)';
  }
}

function timeAgo(ts: number): string {
  const seconds = Math.floor((Date.now() - ts) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

function formatClock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function mapPriority(priority?: string): AlertItem['severity'] {
  switch ((priority ?? '').toUpperCase()) {
    case 'HIGH':
    case 'CRITICAL': return 'high';
    case 'MEDIUM':   return 'medium';
    default:         return 'low';
  }
}

// --- Skeleton loader --------------------------------------------------------

function Skeleton({ width = '100%', height = '16px' }: { width?: string; height?: string }) {
  return (
    <div
      className="terminal-skeleton"
      style={{ width, height, borderRadius: '2px' }}
    />
  );
}

function TableSkeleton({ rows = 4, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', padding: '4px 0' }}>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: '12px' }}>
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} width={c === 0 ? '35%' : '20%'} height="20px" />
          ))}
        </div>
      ))}
    </div>
  );
}

// --- Interfaces -------------------------------------------------------------

interface TopMover {
  securityId: string | null;
  ticker: string;
  name: string;
  price: number;
  changePct: number;
}

interface AlertItem {
  id: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  time: string;
}

interface EconEvent {
  date: string;
  event: string;
  forecast: string;
  prior: string;
}

// --- Backend response shapes ------------------------------------------------

interface MoverEntryDTO {
  rank: number;
  security_id: string | null;
  ticker: string | null;
  name: string | null;
  price: number | null;
  change_pct: number | null;
}
interface MarketMoversDTO {
  snapshot_date: string;
  category: string;
  movers: MoverEntryDTO[];
}
interface AlertEventDTO {
  id: string;
  alert_type: string;
  priority: string;
  entity_id: string;
  title: string;
  created_at: string;
}
interface EconReleaseDTO {
  id: string;
  release_type: string;
  release_category: string;
  release_date: string;
  consensus_value: number | null;
  prior_value: number | null;
}
interface EconCalendarDTO {
  releases: EconReleaseDTO[];
  total_count: number;
}

const fmtNum = (v: number | null | undefined): string =>
  v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: 2 });

// --- Component ---------------------------------------------------------------

export default function MorningBrief() {
  const navigate = useNavigate();
  const setPrimary = useSecurityStore((s) => s.setPrimary);
  const pushHistory = useNavigationStore((s) => s.push);
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now());
  const [, setTick] = useState(0);

  // Top Movers rows render styled like links (accent color) but had no
  // click handler at all -- clicking a ticker did nothing, and since every
  // company-scoped page requires a selected security, that's the most
  // likely reason someone lands on Company/Risk/etc. and sees "No security
  // selected" empty states everywhere despite the backend having real data.
  const goToSecurity = (m: TopMover) => {
    if (!m.securityId) return;
    const security = {
      security_id: m.securityId,
      ticker: m.ticker,
      name: m.name,
      asset_class: 'EQUITY',
      exchange: null,
      figi: null,
      currency: null,
      entity_id: null,
      status: 'ACTIVE',
      gics_sector: null,
      gics_industry: null,
      market_cap: null,
    };
    setPrimary(security);
    pushHistory(security);
    navigate('/company');
  };

  // Tick every 5s to refresh the "last updated" display
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 5_000);
    return () => clearInterval(id);
  }, []);

  // --- API Queries (real endpoints only) ---

  const {
    data: moversData,
    isLoading: loadingMovers,
    isError: moversError,
    dataUpdatedAt: moversUpdatedAt,
  } = useQuery({
    queryKey: ['analytics', 'movers', 'TOP_GAINERS'],
    queryFn: () => api.get<MarketMoversDTO>('/v1/analytics/movers', { category: 'TOP_GAINERS', top_n: 10 }),
    retry: 0,
    staleTime: 60_000,
  });
  const topMovers: TopMover[] = (moversData?.movers ?? [])
    .filter((m) => m.ticker)
    .map((m) => ({
      securityId: m.security_id,
      ticker: m.ticker as string,
      name: m.name ?? '',
      price: m.price ?? 0,
      changePct: m.change_pct ?? 0,
    }));

  const {
    data: alertsData,
    isLoading: loadingAlerts,
    isError: alertsError,
    dataUpdatedAt: alertsUpdatedAt,
  } = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: () => api.get<AlertEventDTO[]>('/v3/alerts'),
    retry: 0,
    staleTime: 60_000,
  });
  const recentAlerts: AlertItem[] = (Array.isArray(alertsData) ? alertsData : []).map((a) => ({
    id: a.id,
    severity: mapPriority(a.priority),
    title: a.title,
    time: formatClock(a.created_at),
  }));

  const {
    data: calendarData,
    isLoading: loadingCalendar,
    isError: calendarError,
    dataUpdatedAt: calendarUpdatedAt,
  } = useQuery({
    queryKey: ['econ', 'calendar'],
    queryFn: () => api.get<EconCalendarDTO>('/v3/news/calendar/economic', { days_ahead: 14 }),
    retry: 0,
    staleTime: 300_000,
  });
  const econCalendar: EconEvent[] = (calendarData?.releases ?? []).map((r) => ({
    date: r.release_date,
    event: r.release_type || r.release_category,
    forecast: fmtNum(r.consensus_value),
    prior: fmtNum(r.prior_value),
  }));

  // Update timestamp when any query succeeds
  useEffect(() => {
    const latest = Math.max(moversUpdatedAt, alertsUpdatedAt, calendarUpdatedAt);
    if (latest > 0) setLastUpdated(latest);
  }, [moversUpdatedAt, alertsUpdatedAt, calendarUpdatedAt]);

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });

  return (
    <>
      {/* Shimmer animation keyframe */}
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        .terminal-skeleton {
          background: linear-gradient(
            90deg,
            var(--color-surface-overlay) 25%,
            var(--color-surface-border) 50%,
            var(--color-surface-overlay) 75%
          );
          background-size: 200% 100%;
          animation: shimmer 1.5s infinite;
        }
      `}</style>

      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        {/* Page header */}
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div>
            <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
              Morning Brief
            </h1>
            <p className="terminal-label" style={{ marginTop: '4px' }}>
              {today} &mdash; Markets &amp; Intelligence Summary
            </p>
          </div>
          <span className="terminal-label" style={{ fontSize: 'var(--text-xs)', whiteSpace: 'nowrap' }}>
            Updated {timeAgo(lastUpdated)}
          </span>
        </div>

        {/* 2-column golden ratio grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

          {/* ---- LEFT COLUMN (65%) ---- */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

            {/* Market Overview — no backend producer for index quotes */}
            <div className="terminal-panel animate-in">
              <h2 className="terminal-section-title">Market Overview</h2>
              <EmptyState
                icon="📈"
                title="Index quotes unavailable"
                description="No live market-index data source is wired to this deployment yet."
              />
            </div>

            {/* Top Movers */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '50ms' }}>
              <h2 className="terminal-section-title">Top Movers</h2>
              {loadingMovers ? (
                <TableSkeleton rows={5} cols={4} />
              ) : moversError || topMovers.length === 0 ? (
                <EmptyState
                  icon="📊"
                  title="No movers available"
                  description="End-of-day price data is required to compute market movers."
                />
              ) : (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Name</th>
                      <th className="right">Price</th>
                      <th className="right">% Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topMovers.map((m) => (
                      <tr
                        key={m.ticker}
                        onClick={() => goToSecurity(m)}
                        style={{ cursor: m.securityId ? 'pointer' : 'default' }}
                      >
                        <td style={{ fontWeight: 600, color: 'var(--color-accent-primary)' }}>{m.ticker}</td>
                        <td className="terminal-label">{m.name}</td>
                        <td className="right">${formatPrice(m.price)}</td>
                        <td className="right" style={{ color: signalColor(m.changePct), fontWeight: 500 }}>
                          {formatPct(m.changePct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Sector Performance — no backend producer */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '100ms' }}>
              <h2 className="terminal-section-title">Sector Performance</h2>
              <EmptyState
                icon="🧭"
                title="Sector performance unavailable"
                description="No market-wide sector-performance endpoint is available yet."
              />
            </div>

            {/* Economic Calendar */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '150ms' }}>
              <h2 className="terminal-section-title">Economic Calendar</h2>
              {loadingCalendar ? (
                <TableSkeleton rows={6} cols={4} />
              ) : calendarError || econCalendar.length === 0 ? (
                <EmptyState
                  icon="🗓️"
                  title="No upcoming releases"
                  description="No economic releases are scheduled in the current window."
                />
              ) : (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th className="right">Date</th>
                      <th>Event</th>
                      <th className="right">Forecast</th>
                      <th className="right">Prior</th>
                    </tr>
                  </thead>
                  <tbody>
                    {econCalendar.map((ev, i) => (
                      <tr key={i}>
                        <td className="right">{ev.date}</td>
                        <td style={{ fontFamily: 'var(--font-ui)' }}>{ev.event}</td>
                        <td className="right">{ev.forecast}</td>
                        <td className="right" style={{ color: 'var(--color-text-secondary)' }}>{ev.prior}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* ---- RIGHT COLUMN (35%) ---- */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

            {/* Alerts */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '75ms' }}>
              <h2 className="terminal-section-title">Alerts</h2>
              {loadingAlerts ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <Skeleton width="6px" height="6px" />
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <Skeleton width="90%" height="14px" />
                        <Skeleton width="30px" height="10px" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : alertsError || recentAlerts.length === 0 ? (
                <EmptyState
                  icon="🔔"
                  title="No recent alerts"
                  description="Fired alert events will appear here."
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {recentAlerts.map((a) => (
                    <div key={a.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                      <span style={{
                        display: 'inline-block',
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: severityColor(a.severity),
                        marginTop: '5px',
                        flexShrink: 0,
                      }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>
                          {a.title}
                        </div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                          {a.time}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
