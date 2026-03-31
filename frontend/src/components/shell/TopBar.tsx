import { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useAlertsStore } from '@/stores/alertsState';
import { useNavigationStore } from '@/stores/navigationHistory';
import { CommandBar } from '../ui/CommandBar';

/* ── Helpers ─────────────────────────────────────────────── */

const APP_VERSION = 'v1.1.0';

/** Live UTC clock string (HH:MM:SS) */
function useUtcClock(): string {
  const [time, setTime] = useState(() => fmtUtc(new Date()));
  useEffect(() => {
    const id = setInterval(() => setTime(fmtUtc(new Date())), 1_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

function fmtUtc(d: Date): string {
  return [d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
}

interface MarketStatus {
  isOpen: boolean;
  label: string;
}

function useMarketStatus(): MarketStatus {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(id);
  }, []);

  const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
  const day = now.getUTCDay();
  const isWeekday = day >= 1 && day <= 5;
  // NYSE: Mon-Fri 13:30-20:00 UTC
  const isOpen = isWeekday && utcMin >= 810 && utcMin < 1200;
  return { isOpen, label: isOpen ? 'Open' : 'Closed' };
}

/** Route path to readable breadcrumb segments */
const ROUTE_LABELS: Record<string, string> = {
  '/': 'Home',
  '/company': 'Company',
  '/company/financials': 'Financials',
  '/company/valuation': 'Valuation',
  '/company/ownership': 'Ownership',
  '/company/filings': 'Filings',
  '/company/credit': 'Credit',
  '/company/intelligence': 'Intelligence',
  '/screener': 'Screener',
  '/screener/fi': 'FI Screener',
  '/sector': 'Sector',
  '/fi': 'Fixed Income',
  '/fi/treasuries': 'Treasuries',
  '/fi/credit': 'Credit Market',
  '/fi/issuance': 'Issuance',
  '/fi/intelligence': 'FI Intelligence',
  '/portfolio': 'Portfolio',
  '/risk': 'Risk',
  '/macro': 'Macro',
  '/macro/yield-curve': 'Yield Curve',
  '/macro/central-banks': 'Central Banks',
  '/global': 'Global',
  '/global/countries': 'Country Risk',
  '/global/commodities': 'Commodities',
  '/global/political': 'Political',
  '/watchlist': 'Watchlist',
  '/alerts': 'Alerts',
  '/news': 'News',
  '/research': 'Research',
  '/research/primers': 'Primers',
  '/research/briefings': 'Briefings',
  '/research/anomalies': 'Anomalies',
  '/research/search': 'Search',
  '/research/thesis': 'Thesis Builder',
  '/research/qa': 'Analyst QA',
  '/research/themes': 'Themes',
  '/flows': 'Flows',
  '/custom': 'Custom Data',
  '/settings': 'Settings',
};

function useBreadcrumbs(): string[] {
  const { pathname } = useLocation();
  return useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    const crumbs: string[] = [];
    let path = '';
    for (const seg of segments) {
      path += '/' + seg;
      const label = ROUTE_LABELS[path];
      if (label) {
        crumbs.push(label);
      } else {
        crumbs.push(decodeURIComponent(seg));
      }
    }
    return crumbs.length > 0 ? crumbs : ['Home'];
  }, [pathname]);
}

/* ── Component ───────────────────────────────────────────── */

export function TopBar() {
  const primary = useSecurityStore((s) => s.primary);
  const unread = useAlertsStore((s) => s.unread);
  const stack = useNavigationStore((s) => s.stack);
  const recent = useMemo(() => stack.slice(-5), [stack]);
  const utcClock = useUtcClock();
  const market = useMarketStatus();
  const breadcrumbs = useBreadcrumbs();

  const [commandBarOpen, setCommandBarOpen] = useState(false);

  // Cmd/Ctrl+K shortcut
  const handleKey = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      setCommandBarOpen((prev) => !prev);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  const hasUnread = unread.length > 0;

  return (
    <>
      <header
        className="flex items-center h-10 px-3 bg-surface-base border-b border-surface-border gap-2"
        style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)' }}
      >
        {/* ── Logo ── */}
        <div className="flex items-center gap-2 shrink-0">
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            className="shrink-0"
            aria-label="Bloomberg Data Fabric"
          >
            <path
              d="M12 2L22 12L12 22L2 12Z"
              fill="var(--color-accent-primary)"
              opacity="0.85"
            />
            <path
              d="M12 5L19 12L12 19L5 12Z"
              fill="var(--color-surface-base)"
              opacity="0.5"
            />
            <text
              x="12"
              y="15.5"
              textAnchor="middle"
              fill="white"
              fontSize="9"
              fontWeight="700"
              fontFamily="var(--font-ui)"
            >
              B
            </text>
          </svg>
          <span className="text-text-secondary text-xs font-ui hidden lg:inline tracking-wider">
            DATA FABRIC
          </span>
        </div>

        {/* ── Breadcrumb ── */}
        <nav
          className="hidden md:flex items-center gap-1 text-text-tertiary shrink-0"
          aria-label="Breadcrumb"
          style={{ fontSize: 'var(--text-xs)' }}
        >
          {breadcrumbs.map((crumb, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && (
                <svg width="10" height="10" viewBox="0 0 10 10" className="text-text-tertiary opacity-50">
                  <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.2" fill="none" />
                </svg>
              )}
              <span className={i === breadcrumbs.length - 1 ? 'text-text-secondary' : ''}>
                {crumb}
              </span>
            </span>
          ))}
          {primary && (
            <>
              <svg width="10" height="10" viewBox="0 0 10 10" className="text-text-tertiary opacity-50">
                <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.2" fill="none" />
              </svg>
              <span className="text-accent-primary font-data font-semibold">
                {primary.ticker}
              </span>
            </>
          )}
        </nav>

        {/* ── Search Trigger ── */}
        <button
          className="flex-1 max-w-xl h-7 px-3 bg-surface-void border border-surface-border rounded flex items-center gap-2 text-left group"
          onClick={() => setCommandBarOpen(true)}
          style={{ transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-accent-primary)';
            e.currentTarget.style.boxShadow = '0 0 8px var(--accent-glow)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = '';
            e.currentTarget.style.boxShadow = '';
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" className="text-text-tertiary shrink-0">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" fill="none" />
            <path d="M16 16L21 21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span className="font-ui text-text-tertiary text-xs truncate">
            Search securities, commands...
          </span>
          <span
            className="ml-auto shrink-0 px-1.5 py-0.5 rounded text-text-tertiary font-data"
            style={{
              fontSize: '9px',
              border: '1px solid var(--color-surface-border-strong)',
              background: 'var(--color-surface-raised)',
              lineHeight: 1.2,
            }}
          >
            {'\u2318'}K
          </span>
        </button>

        {/* ── Recent Tickers (chips) ── */}
        <div className="hidden xl:flex items-center gap-1">
          {recent.slice(0, 3).map((sec, i) => (
            <button
              key={i}
              className="px-2 py-0.5 rounded font-data text-xs text-text-tertiary"
              style={{
                fontSize: 'var(--text-xs)',
                background: 'var(--color-surface-raised)',
                border: '1px solid var(--color-surface-border)',
                transition: 'all var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-accent-primary)';
                e.currentTarget.style.color = 'var(--color-text-primary)';
                e.currentTarget.style.background = 'var(--color-surface-overlay)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '';
                e.currentTarget.style.color = '';
                e.currentTarget.style.background = '';
              }}
            >
              {sec.ticker}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {/* ── Market Indicator + Clock ── */}
        <div
          className="hidden sm:flex items-center gap-2 shrink-0"
          style={{ fontSize: 'var(--text-xs)' }}
        >
          <span className="flex items-center gap-1 font-ui">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{
                background: market.isOpen
                  ? 'var(--color-signal-positive)'
                  : 'var(--color-text-tertiary)',
              }}
            />
            <span
              style={{
                color: market.isOpen
                  ? 'var(--color-signal-positive)'
                  : 'var(--color-text-tertiary)',
              }}
            >
              Mkt: {market.label}
            </span>
          </span>
          <span
            className="font-data text-text-secondary"
            style={{ letterSpacing: '0.04em' }}
          >
            {utcClock}
            <span className="text-text-tertiary ml-0.5">UTC</span>
          </span>
        </div>

        {/* ── Alerts Badge ── */}
        <button className="relative p-1.5 rounded" style={{ transition: 'background var(--transition-fast)' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-overlay)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
        >
          <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          {hasUnread && (
            <span
              className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-white flex items-center justify-center"
              style={{
                fontSize: '9px',
                fontWeight: 700,
                background: 'var(--color-signal-negative)',
                animation: 'alertPulse 2s ease-in-out infinite',
              }}
            >
              {unread.length > 99 ? '99+' : unread.length}
            </span>
          )}
        </button>

        {/* ── Version + "What's New" ── */}
        <span
          className="hidden lg:flex items-center gap-1 font-data text-text-tertiary shrink-0"
          style={{ fontSize: '9px' }}
        >
          {APP_VERSION}
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--color-accent-primary)' }}
            title="What's New"
          />
        </span>

        {/* ── User Avatar ── */}
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-text-secondary text-xs font-bold shrink-0"
          style={{
            background: 'var(--color-surface-overlay)',
            transition: 'background var(--transition-fast)',
          }}
        >
          U
        </div>
      </header>

      {/* Pulse animation for alerts */}
      <style>{`
        @keyframes alertPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(224,82,82,0.5); }
          50%       { box-shadow: 0 0 0 4px rgba(224,82,82,0); }
        }
      `}</style>

      {/* Command Bar */}
      <CommandBar open={commandBarOpen} onClose={() => setCommandBarOpen(false)} />
    </>
  );
}
