import { useState, useEffect } from 'react';

function useMarketStatus(): { label: string; isOpen: boolean } {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const utcH = now.getUTCHours();
  const utcM = now.getUTCMinutes();
  const utcDay = now.getUTCDay();
  // NYSE: Mon-Fri 13:30-20:00 UTC (9:30-16:00 ET)
  const minutesUTC = utcH * 60 + utcM;
  const isWeekday = utcDay >= 1 && utcDay <= 5;
  const isOpen = isWeekday && minutesUTC >= 810 && minutesUTC < 1200;
  return { label: isOpen ? 'US Markets: Open' : 'US Markets: Closed', isOpen };
}

export function StatusBar() {
  const connected = true; // placeholder — swap for real WS health check
  const market = useMarketStatus();

  return (
    <footer
      style={{
        display: 'flex',
        alignItems: 'center',
        height: '22px',
        padding: '0 12px',
        background: 'var(--color-surface-base)',
        borderTop: '1px solid var(--color-surface-border)',
        fontFamily: 'var(--font-ui)',
        fontSize: '10px',
        color: 'var(--color-text-tertiary)',
        gap: '12px',
      }}
    >
      {/* Connection status */}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: connected ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)',
            display: 'inline-block',
          }}
        />
        {connected ? 'Connected' : 'Disconnected'}
      </span>

      {/* Market status */}
      <span style={{ color: market.isOpen ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)' }}>
        {market.label}
      </span>

      {/* Timestamp */}
      <span>Data as of: {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC</span>

      <div style={{ flex: 1 }} />

      <span style={{ fontFamily: 'var(--font-data)' }}>/ to search</span>
      <span>&bull;</span>
      <span style={{ fontFamily: 'var(--font-data)' }}>? for shortcuts</span>
      <span>&bull;</span>
      <span style={{ fontFamily: 'var(--font-data)' }}>v1.0.0</span>
    </footer>
  );
}
