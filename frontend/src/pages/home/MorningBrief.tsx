// ---------------------------------------------------------------------------
// Morning Brief -- Landing Page
// React Query integration with graceful fallback to mock data
// ---------------------------------------------------------------------------

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

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
    case 'low':    return 'var(--color-signal-neutral)';
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

interface MarketIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

interface TopMover {
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
  time: string;
  event: string;
  forecast: string;
  prior: string;
}

interface SectorPerf {
  sector: string;
  d1: number;
  w1: number;
  m1: number;
}

// --- Mock Data (fallback) ---------------------------------------------------

const MOCK_MARKET_INDICES: MarketIndex[] = [
  { name: 'S&P 500',      value: 5248.72, change: 18.34,   changePct: 0.35 },
  { name: 'DJIA',         value: 39142.50, change: -42.18, changePct: -0.11 },
  { name: 'NASDAQ',       value: 16432.85, change: 87.62,  changePct: 0.54 },
  { name: '10Y Treasury', value: 4.278,    change: -0.032, changePct: -0.74 },
];

const MOCK_TOP_MOVERS: TopMover[] = [
  { ticker: 'NVDA', name: 'NVIDIA Corp',      price: 878.36, changePct: 4.82 },
  { ticker: 'SMCI', name: 'Super Micro Comp',  price: 932.10, changePct: 3.67 },
  { ticker: 'META', name: 'Meta Platforms',     price: 503.28, changePct: 2.41 },
  { ticker: 'INTC', name: 'Intel Corp',         price: 31.42,  changePct: -4.15 },
  { ticker: 'PFE',  name: 'Pfizer Inc',         price: 26.88,  changePct: -3.28 },
];

const MOCK_ALERTS: AlertItem[] = [
  { id: '1', severity: 'high',   title: 'AAPL — Earnings miss: EPS $1.52 vs est. $1.58',       time: '08:32' },
  { id: '2', severity: 'medium', title: 'UST 10Y yield breached 4.30% level',                   time: '09:15' },
  { id: '3', severity: 'low',    title: 'MSFT — New insider purchase filed (Form 4)',            time: '10:02' },
  { id: '4', severity: 'medium', title: 'VIX spiked above 18 — elevated volatility regime',     time: '10:47' },
  { id: '5', severity: 'high',   title: 'JPM — CDS spread widened 12 bps in 24h',               time: '11:20' },
];

const MOCK_ECON_CALENDAR: EconEvent[] = [
  { date: '2026-03-27', time: '08:30', event: 'Initial Jobless Claims',        forecast: '212K', prior: '209K' },
  { date: '2026-03-27', time: '10:00', event: 'Pending Home Sales MoM',        forecast: '1.5%', prior: '-4.9%' },
  { date: '2026-03-28', time: '08:30', event: 'Core PCE Price Index YoY',      forecast: '2.8%', prior: '2.8%' },
  { date: '2026-03-28', time: '10:00', event: 'Michigan Consumer Sentiment',   forecast: '76.5', prior: '76.9' },
  { date: '2026-03-31', time: '09:45', event: 'Chicago PMI',                   forecast: '46.0', prior: '44.0' },
  { date: '2026-03-31', time: '10:30', event: 'Dallas Fed Manufacturing',      forecast: '-8.0', prior: '-11.3' },
];

const MOCK_SECTOR_PERF: SectorPerf[] = [
  { sector: 'Information Technology', d1:  0.82, w1:  1.45, m1:  3.21 },
  { sector: 'Health Care',            d1: -0.34, w1: -0.92, m1:  1.12 },
  { sector: 'Financials',             d1:  0.51, w1:  0.78, m1:  2.44 },
  { sector: 'Consumer Discretionary', d1:  0.23, w1: -0.15, m1:  0.67 },
  { sector: 'Communication Services', d1:  1.14, w1:  2.03, m1:  4.58 },
  { sector: 'Industrials',            d1:  0.09, w1:  0.34, m1:  1.78 },
  { sector: 'Consumer Staples',       d1: -0.18, w1: -0.55, m1: -0.23 },
  { sector: 'Energy',                 d1: -0.72, w1: -1.88, m1: -3.14 },
  { sector: 'Utilities',              d1:  0.15, w1:  0.42, m1:  0.91 },
  { sector: 'Real Estate',            d1: -0.41, w1: -1.23, m1: -2.07 },
  { sector: 'Materials',              d1:  0.06, w1: -0.31, m1:  0.44 },
];

// --- Component ---------------------------------------------------------------

export default function MorningBrief() {
  // Track last successful data fetch timestamp
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now());
  const [, setTick] = useState(0);

  // Tick every 5s to refresh the "last updated" display
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 5_000);
    return () => clearInterval(id);
  }, []);

  // --- API Queries with graceful fallback ---

  const { data: marketData, isLoading: loadingMarket, dataUpdatedAt: marketUpdatedAt } = useQuery({
    queryKey: ['market', 'indices'],
    queryFn: () => api.get<MarketIndex[]>('/v1/market/indices'),
    retry: 0,
    staleTime: 30_000,
  });
  const marketIndices = marketData ?? MOCK_MARKET_INDICES;

  const { data: moversData, isLoading: loadingMovers, dataUpdatedAt: moversUpdatedAt } = useQuery({
    queryKey: ['market', 'movers'],
    queryFn: () => api.get<TopMover[]>('/v1/market/movers'),
    retry: 0,
    staleTime: 30_000,
  });
  const topMovers = moversData ?? MOCK_TOP_MOVERS;

  const { data: alertsData, isLoading: loadingAlerts, dataUpdatedAt: alertsUpdatedAt } = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: () => api.get<AlertItem[]>('/v1/alerts/recent'),
    retry: 0,
    staleTime: 60_000,
  });
  const recentAlerts = alertsData ?? MOCK_ALERTS;

  const { data: calendarData, isLoading: loadingCalendar, dataUpdatedAt: calendarUpdatedAt } = useQuery({
    queryKey: ['econ', 'calendar'],
    queryFn: () => api.get<EconEvent[]>('/v1/econ/calendar'),
    retry: 0,
    staleTime: 300_000,
  });
  const econCalendar = calendarData ?? MOCK_ECON_CALENDAR;

  const { data: sectorData, isLoading: loadingSectors, dataUpdatedAt: sectorUpdatedAt } = useQuery({
    queryKey: ['market', 'sectors'],
    queryFn: () => api.get<SectorPerf[]>('/v1/market/sectors'),
    retry: 0,
    staleTime: 60_000,
  });
  const sectorPerf = sectorData ?? MOCK_SECTOR_PERF;

  // Update timestamp when any query succeeds
  useEffect(() => {
    const latest = Math.max(marketUpdatedAt, moversUpdatedAt, alertsUpdatedAt, calendarUpdatedAt, sectorUpdatedAt);
    if (latest > 0) setLastUpdated(latest);
  }, [marketUpdatedAt, moversUpdatedAt, alertsUpdatedAt, calendarUpdatedAt, sectorUpdatedAt]);

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
              Thursday, March 27 2026 &mdash; Markets &amp; Intelligence Summary
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

            {/* Market Overview */}
            <div className="terminal-panel animate-in">
              <h2 className="terminal-section-title">Market Overview</h2>
              {loadingMarket ? (
                <TableSkeleton rows={4} cols={4} />
              ) : (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>Index</th>
                      <th className="right">Last</th>
                      <th className="right">Change</th>
                      <th className="right">% Chg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {marketIndices.map((idx) => (
                      <tr key={idx.name}>
                        <td style={{ fontWeight: 500 }}>{idx.name}</td>
                        <td className="right">{formatPrice(idx.value)}</td>
                        <td className="right" style={{ color: signalColor(idx.change) }}>
                          {idx.change >= 0 ? '+' : ''}{idx.change.toFixed(2)}
                        </td>
                        <td className="right" style={{ color: signalColor(idx.changePct) }}>
                          {formatPct(idx.changePct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Top Movers */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '50ms' }}>
              <h2 className="terminal-section-title">Top Movers</h2>
              {loadingMovers ? (
                <TableSkeleton rows={5} cols={4} />
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
                      <tr key={m.ticker}>
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

            {/* Sector Performance */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '100ms' }}>
              <h2 className="terminal-section-title">Sector Performance</h2>
              {loadingSectors ? (
                <TableSkeleton rows={11} cols={4} />
              ) : (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>GICS Sector</th>
                      <th className="right">1D %</th>
                      <th className="right">1W %</th>
                      <th className="right">1M %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectorPerf.map((s) => (
                      <tr key={s.sector}>
                        <td style={{ fontWeight: 500 }}>{s.sector}</td>
                        <td className="right" style={{ color: signalColor(s.d1) }}>{formatPct(s.d1)}</td>
                        <td className="right" style={{ color: signalColor(s.w1) }}>{formatPct(s.w1)}</td>
                        <td className="right" style={{ color: signalColor(s.m1) }}>{formatPct(s.m1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Economic Calendar */}
            <div className="terminal-panel animate-in" style={{ animationDelay: '150ms' }}>
              <h2 className="terminal-section-title">Economic Calendar</h2>
              {loadingCalendar ? (
                <TableSkeleton rows={6} cols={5} />
              ) : (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th className="right">Date</th>
                      <th className="right">Time</th>
                      <th>Event</th>
                      <th className="right">Forecast</th>
                      <th className="right">Prior</th>
                    </tr>
                  </thead>
                  <tbody>
                    {econCalendar.map((ev, i) => (
                      <tr key={i}>
                        <td className="right">{ev.date}</td>
                        <td className="right">{ev.time}</td>
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
