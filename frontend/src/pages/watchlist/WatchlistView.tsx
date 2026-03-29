// ---------------------------------------------------------------------------
// Watchlist View — Watchlist Management, Monitoring Alerts, Earnings Calendar
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { WatchlistManager, EarningsCalendarWidget } from '@/components/alerts';
import type { WatchlistEntity, EarningsEvent } from '@/components/alerts';

const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

const watchlistItems = [
  { ticker: 'AAPL', name: 'Apple Inc.', price: 178.72, chg: -0.34, pe: 28.6, mktCap: '2.78T', alert: 'Earnings 4/25' },
  { ticker: 'MSFT', name: 'Microsoft Corp', price: 422.15, chg: 0.82, pe: 34.2, mktCap: '3.12T', alert: 'Earnings 4/22' },
  { ticker: 'NVDA', name: 'NVIDIA Corp', price: 878.36, chg: 4.82, pe: 62.5, mktCap: '2.18T', alert: 'Price > $875' },
  { ticker: 'GOOGL', name: 'Alphabet Inc.', price: 155.42, chg: 1.15, pe: 24.5, mktCap: '2.05T', alert: '' },
  { ticker: 'JPM', name: 'JPMorgan Chase', price: 195.80, chg: -0.52, pe: 11.8, mktCap: '$570B', alert: 'CDS widening' },
  { ticker: 'AMZN', name: 'Amazon.com', price: 182.50, chg: 0.95, pe: 58.3, mktCap: '1.92T', alert: '' },
  { ticker: 'META', name: 'Meta Platforms', price: 503.28, chg: 2.41, pe: 22.8, mktCap: '1.28T', alert: '' },
];

const earningsCalendar = [
  { date: '2026-04-15', ticker: 'JPM', name: 'JPMorgan Chase', time: 'BMO', epsEst: '$4.52', impliedMove: '3.2%' },
  { date: '2026-04-22', ticker: 'MSFT', name: 'Microsoft', time: 'AMC', epsEst: '$3.18', impliedMove: '4.5%' },
  { date: '2026-04-25', ticker: 'AAPL', name: 'Apple', time: 'AMC', epsEst: '$1.62', impliedMove: '3.8%' },
  { date: '2026-04-25', ticker: 'GOOGL', name: 'Alphabet', time: 'AMC', epsEst: '$1.89', impliedMove: '5.1%' },
  { date: '2026-04-30', ticker: 'AMZN', name: 'Amazon', time: 'AMC', epsEst: '$1.05', impliedMove: '6.2%' },
];

// --- Component Data ----------------------------------------------------------

const initialEntities: WatchlistEntity[] = watchlistItems.map((w, i) => ({
  id: `w-${i}`,
  ticker: w.ticker,
  name: w.name,
  alertsEnabled: {
    price: true,
    filing: w.ticker === 'AAPL' || w.ticker === 'MSFT',
    earnings: !!w.alert?.includes('Earnings'),
    score: false,
  },
}));

const earningsEvents: EarningsEvent[] = earningsCalendar.map((e, i) => ({
  id: `ec-${i}`,
  date: e.date,
  ticker: e.ticker,
  companyName: e.name,
  expectedEps: parseFloat(e.epsEst.replace('$', '')),
  time: e.time as EarningsEvent['time'],
}));

export default function WatchlistView() {
  const [entities, setEntities] = useState<WatchlistEntity[]>(initialEntities);

  const handleAdd = useCallback(() => {
    // placeholder — would open an entity search dialog
  }, []);

  const handleRemove = useCallback((id: string) => {
    setEntities((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const handleReorder = useCallback((fromIdx: number, toIdx: number) => {
    setEntities((prev) => {
      const next = [...prev];
      const [item] = next.splice(fromIdx, 1);
      if (item) next.splice(toIdx, 0, item);
      return next;
    });
  }, []);

  const handleToggleAlert = useCallback((id: string, alertType: keyof WatchlistEntity['alertsEnabled']) => {
    setEntities((prev) =>
      prev.map((e) =>
        e.id === id ? { ...e, alertsEnabled: { ...e.alertsEnabled, [alertType]: !e.alertsEnabled[alertType] } } : e,
      ),
    );
  }, []);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Watchlist</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Core Holdings &mdash; {entities.length} securities monitored</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* WatchlistManager — replaces inline table */}
        <WatchlistManager
          entities={entities}
          onAdd={handleAdd}
          onRemove={handleRemove}
          onReorder={handleReorder}
          onToggleAlert={handleToggleAlert}
        />
        {/* EarningsCalendarWidget — replaces inline earnings table */}
        <EarningsCalendarWidget
          events={earningsEvents}
          watchlistTickers={entities.map((e) => e.ticker)}
        />
      </div>
    </div>
  );
}
