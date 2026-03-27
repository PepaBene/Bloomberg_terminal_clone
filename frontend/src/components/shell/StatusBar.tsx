import { useState, useEffect, useMemo } from 'react';

/* ── Hooks ───────────────────────────────────────────────── */

interface MarketInfo {
  label: string;
  isOpen: boolean;
  countdown: string | null;
}

function useMarketStatus(): MarketInfo {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 10_000);
    return () => clearInterval(id);
  }, []);

  const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
  const day = now.getUTCDay();
  const isWeekday = day >= 1 && day <= 5;
  // NYSE: Mon-Fri 13:30-20:00 UTC (9:30-16:00 ET)
  const isOpen = isWeekday && utcMin >= 810 && utcMin < 1200;

  let countdown: string | null = null;
  if (isOpen) {
    const minsLeft = 1200 - utcMin;
    const h = Math.floor(minsLeft / 60);
    const m = minsLeft % 60;
    countdown = h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  return {
    label: isOpen ? 'US Markets: Open' : 'US Markets: Closed',
    isOpen,
    countdown,
  };
}

function useFormattedDate(): string {
  return useMemo(() => {
    const d = new Date();
    const months = [
      'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
      'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
    ] as const;
    const day = String(d.getUTCDate()).padStart(2, '0');
    const mon = months[d.getUTCMonth()];
    const year = d.getUTCFullYear();
    return `${day} ${mon} ${year}`;
  }, []);
}

interface PerfMetrics {
  memory: string | null;
}

function usePerfMetrics(): PerfMetrics {
  const [mem, setMem] = useState<string | null>(null);
  useEffect(() => {
    function measure() {
      const perf = performance as Performance & {
        memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number };
      };
      if (perf.memory) {
        const usedMB = Math.round(perf.memory.usedJSHeapSize / (1024 * 1024));
        setMem(`${usedMB}MB`);
      }
    }
    measure();
    const id = setInterval(measure, 15_000);
    return () => clearInterval(id);
  }, []);
  return { memory: mem };
}

/* ── Shared inline styles ────────────────────────────────── */

const kbdStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '0 4px',
  height: '14px',
  borderRadius: '3px',
  border: '1px solid var(--color-surface-border-strong)',
  background: 'var(--color-surface-raised)',
  fontFamily: 'var(--font-data)',
  fontSize: '9px',
  lineHeight: 1,
  color: 'var(--color-text-tertiary)',
  boxShadow: '0 1px 0 var(--color-surface-border)',
};

/* ── Component ───────────────────────────────────────────── */

export function StatusBar() {
  const connected = true; // placeholder -- swap for real WS health check
  const market = useMarketStatus();
  const dateStr = useFormattedDate();
  const perf = usePerfMetrics();

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
      {/* Connection status with pulse */}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: connected
              ? 'var(--color-signal-positive)'
              : 'var(--color-signal-negative)',
            display: 'inline-block',
            animation: connected ? 'statusPulse 3s ease-in-out infinite' : 'none',
          }}
        />
        {connected ? 'Connected' : 'Disconnected'}
      </span>

      {/* Separator */}
      <span style={{ color: 'var(--color-surface-border-strong)' }}>&bull;</span>

      {/* Market status + countdown */}
      <span
        style={{
          color: market.isOpen
            ? 'var(--color-signal-positive)'
            : 'var(--color-text-tertiary)',
        }}
      >
        {market.label}
        {market.countdown && (
          <span style={{ marginLeft: '4px', fontFamily: 'var(--font-data)' }}>
            Closes in {market.countdown}
          </span>
        )}
      </span>

      <span style={{ color: 'var(--color-surface-border-strong)' }}>&bull;</span>

      {/* Current date */}
      <span style={{ fontFamily: 'var(--font-data)', letterSpacing: '0.04em' }}>
        {dateStr}
      </span>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Performance indicator */}
      {perf.memory && (
        <>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              fontFamily: 'var(--font-data)',
              fontSize: '9px',
              color: 'var(--color-text-tertiary)',
            }}
          >
            <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="6" width="3" height="9" rx="0.5" fill="var(--color-text-tertiary)" opacity="0.5" />
              <rect x="5" y="3" width="3" height="12" rx="0.5" fill="var(--color-text-tertiary)" opacity="0.65" />
              <rect x="9" y="1" width="3" height="14" rx="0.5" fill="var(--color-text-tertiary)" opacity="0.8" />
              <rect x="13" y="5" width="3" height="10" rx="0.5" fill="var(--color-text-tertiary)" opacity="0.4" />
            </svg>
            {perf.memory}
          </span>
          <span style={{ color: 'var(--color-surface-border-strong)' }}>&bull;</span>
        </>
      )}

      {/* Keyboard hints as key badges */}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
          <kbd style={kbdStyle}>/</kbd>
          <span>search</span>
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
          <kbd style={kbdStyle}>?</kbd>
          <span>shortcuts</span>
        </span>
      </span>

      <span style={{ color: 'var(--color-surface-border-strong)' }}>&bull;</span>

      {/* Version */}
      <span style={{ fontFamily: 'var(--font-data)' }}>v1.1.0</span>

      {/* Pulse animation */}
      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(45,184,125,0.45); }
          50%       { opacity: 0.7; box-shadow: 0 0 0 3px rgba(45,184,125,0); }
        }
      `}</style>
    </footer>
  );
}
