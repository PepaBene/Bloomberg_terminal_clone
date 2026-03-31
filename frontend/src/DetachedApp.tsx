/**
 * DetachedApp — minimal root for Tauri/browser detached panel windows.
 * Reads panel type from window.location.hash (#detached/<panelId>)
 * and renders the appropriate component without the shell navigation.
 */
import React, { Suspense, lazy } from 'react';
import type { CSSProperties } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

/* ── Panel registry ────────────────────────────────────────── */

const PANELS: Record<string, React.LazyExoticComponent<() => React.ReactElement>> = {
  company:      lazy(() => import('@/pages/company/CompanyOverview')),
  financials:   lazy(() => import('@/pages/company/FinancialStatements')),
  valuation:    lazy(() => import('@/pages/company/ValuationDashboard')),
  screener:     lazy(() => import('@/pages/screener/ScreenerDashboard')),
  fi:           lazy(() => import('@/pages/fi/FIDashboard')),
  portfolio:    lazy(() => import('@/pages/portfolio/PortfolioList')),
  risk:         lazy(() => import('@/pages/risk/RiskDashboard')),
  macro:        lazy(() => import('@/pages/macro/MacroDashboard')),
  news:         lazy(() => import('@/pages/news/NewsView')),
  alerts:       lazy(() => import('@/pages/alerts/AlertsView')),
  research:     lazy(() => import('@/pages/research/ResearchHub')),
  watchlist:    lazy(() => import('@/pages/watchlist/WatchlistView')),
};

function getDetachedPanelId(): string | null {
  const hash = window.location.hash;
  if (!hash.startsWith('#detached/')) return null;
  return hash.replace('#detached/', '') || null;
}

function DetachedShell() {
  const panelId = getDetachedPanelId();

  const shellStyle: CSSProperties = {
    width: '100vw',
    height: '100vh',
    background: 'var(--color-surface-void)',
    overflow: 'hidden',
  };

  if (!panelId) {
    return (
      <div style={{ ...shellStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-text-tertiary)' }}>
          No panel specified
        </span>
      </div>
    );
  }

  const PanelComponent = PANELS[panelId];

  if (!PanelComponent) {
    return (
      <div style={{ ...shellStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-text-tertiary)' }}>
          Unknown panel: {panelId}
        </span>
      </div>
    );
  }

  return (
    <div style={shellStyle}>
      <Suspense fallback={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
            Loading…
          </span>
        </div>
      }>
        <PanelComponent />
      </Suspense>
    </div>
  );
}

export default function DetachedApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DetachedShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
