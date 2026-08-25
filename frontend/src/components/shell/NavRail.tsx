import { useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react';

/* ── SVG Icon Components (16x16, stroke-based, Lucide-style) ── */

interface IconProps {
  filled?: boolean;
}

const s = { width: 16, height: 16, strokeWidth: 1.5, stroke: 'currentColor', fill: 'none' } as const;
const sf = { width: 16, height: 16, strokeWidth: 1.5, stroke: 'currentColor' } as const;

function IconHome({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M2 6.5L8 2l6 4.5V13a1 1 0 01-1 1H3a1 1 0 01-1-1V6.5z" />
      <path d="M6 14V9h4v5" fill="none" />
    </svg>
  );
}

function IconScreener({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <rect x="2" y="2" width="5" height="5" rx="0.5" />
      <rect x="9" y="2" width="5" height="5" rx="0.5" />
      <rect x="2" y="9" width="5" height="5" rx="0.5" />
      <rect x="9" y="9" width="5" height="5" rx="0.5" />
    </svg>
  );
}

function IconCompany({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M2 14V3a1 1 0 011-1h6a1 1 0 011 1v11" />
      <path d="M10 8h3a1 1 0 011 1v5" />
      <path d="M2 14h12" fill="none" />
      <path d="M4.5 4.5h1M4.5 7h1M4.5 9.5h1M7 4.5h1M7 7h1M7 9.5h1" fill="none" />
    </svg>
  );
}

function IconSector({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M8 2a6 6 0 110 12 6 6 0 010-12z" />
      <path d="M8 2v6l4.24 4.24" fill="none" />
    </svg>
  );
}

function IconFixedIncome({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M2 4l3.5 3L8 5l3 2.5L14 4" fill="none" />
      <path d="M2 8.5l3.5 3L8 9.5l3 2.5L14 8.5" fill="none" />
      <line x1="2" y1="13" x2="14" y2="13" fill="none" />
    </svg>
  );
}

function IconPortfolio({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <rect x="2" y="5" width="12" height="9" rx="1" />
      <path d="M5 5V3.5A1.5 1.5 0 016.5 2h3A1.5 1.5 0 0111 3.5V5" fill="none" />
      <line x1="2" y1="9" x2="14" y2="9" fill="none" />
    </svg>
  );
}

function IconRisk({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M8 1.5l6 3.5v4c0 3.5-2.5 5.5-6 7-3.5-1.5-6-3.5-6-7V5L8 1.5z" />
      <path d="M8 5v3.5M8 10.5h.01" fill="none" />
    </svg>
  );
}

function IconMacro({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <circle cx="8" cy="8" r="6" />
      <path d="M2 8h12M8 2a10 10 0 013 6 10 10 0 01-3 6M8 2a10 10 0 00-3 6 10 10 0 003 6" fill="none" />
    </svg>
  );
}

function IconGlobal({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <circle cx="8" cy="8" r="6" />
      <ellipse cx="8" cy="8" rx="2.5" ry="6" fill="none" />
      <line x1="2" y1="6" x2="14" y2="6" fill="none" />
      <line x1="2" y1="10" x2="14" y2="10" fill="none" />
    </svg>
  );
}

function IconNews({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <rect x="2" y="2" width="10" height="12" rx="1" />
      <path d="M12 5h1.5a.5.5 0 01.5.5V13a1 1 0 01-1 1H4" fill="none" />
      <line x1="4.5" y1="5" x2="9.5" y2="5" fill="none" />
      <line x1="4.5" y1="7.5" x2="9.5" y2="7.5" fill="none" />
      <line x1="4.5" y1="10" x2="7" y2="10" fill="none" />
    </svg>
  );
}

function IconResearch({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M6 14v-3a2 2 0 012-2h0a2 2 0 012 2v3" fill="none" />
      <circle cx="8" cy="5.5" r="3.5" />
      <line x1="8" y1="3" x2="8" y2="5.5" fill="none" />
      <line x1="6.5" y1="5.5" x2="9.5" y2="5.5" fill="none" />
    </svg>
  );
}

function IconFlows({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <polyline points="2,8 4.5,4 6.5,10 8.5,3 10.5,11 12.5,6 14,8" fill="none" />
    </svg>
  );
}

function IconWatchlist({ filled }: IconProps) {
  return (
    <svg {...sf} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M8 1.5l1.76 3.57 3.94.57-2.85 2.78.67 3.93L8 10.5l-3.52 1.85.67-3.93L2.3 5.64l3.94-.57L8 1.5z" />
    </svg>
  );
}

function IconAlerts({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M6 13a2 2 0 004 0" fill="none" />
      <path d="M8 1.5a.75.75 0 01.75.75v.5A4.25 4.25 0 0112.5 7v2.5l1 1.5H2.5l1-1.5V7a4.25 4.25 0 013.75-4.25v-.5A.75.75 0 018 1.5z" />
    </svg>
  );
}

function IconSmartMoney({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.5v7M10 6.3c0-1-.9-1.8-2-1.8s-2 .75-2 1.7c0 2.1 4 1.05 4 3.15 0 .95-.9 1.7-2 1.7s-2-.8-2-1.8" fill="none" />
    </svg>
  );
}

function IconDashboard({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <rect x="2" y="2" width="7" height="5" rx="0.5" />
      <rect x="2" y="9" width="7" height="5" rx="0.5" />
      <rect x="11" y="2" width="3" height="12" rx="0.5" />
    </svg>
  );
}

function IconAdviser({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <path d="M2 3.5a1 1 0 011-1h10a1 1 0 011 1v6a1 1 0 01-1 1H6.5L3 13v-2.5H3a1 1 0 01-1-1v-6z" />
      <path d="M5 6h6M5 8.5h3.5" fill="none" />
    </svg>
  );
}

function IconSettings({ filled }: IconProps) {
  return (
    <svg {...(filled ? sf : s)} viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'}>
      <circle cx="8" cy="8" r="2" />
      <path
        d="M8 1.5l.65 1.84a4.5 4.5 0 011.5.87l1.87-.53.75 1.3-1.22 1.37a4.5 4.5 0 010 1.3l1.22 1.37-.75 1.3-1.87-.53a4.5 4.5 0 01-1.5.87L8 14.5l-.65-1.84a4.5 4.5 0 01-1.5-.87l-1.87.53-.75-1.3 1.22-1.37a4.5 4.5 0 010-1.3L3.23 6.98l.75-1.3 1.87.53a4.5 4.5 0 011.5-.87L8 1.5z"
        fill="none"
      />
    </svg>
  );
}

/* ── Nav item data model ──────────────────────────────────── */

interface NavItemDef {
  id: string;
  icon: (props: IconProps) => ReactNode;
  label: string;
  path: string;
  shortcut: string;
  subItems?: string[];
}

interface NavGroup {
  id: string;
  label?: string;
  items: NavItemDef[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: 'home',
    items: [
      { id: 'home', icon: IconHome, label: 'Home', path: '/', shortcut: '1', subItems: ['Dashboard', 'Overview'] },
    ],
  },
  {
    id: 'analysis',
    label: 'Analysis',
    items: [
      { id: 'screener', icon: IconScreener, label: 'Screener', path: '/screener', shortcut: '2', subItems: ['Equity', 'Fixed Income', 'Custom'] },
      { id: 'company', icon: IconCompany, label: 'Company', path: '/company', shortcut: '3', subItems: ['Profile', 'Financials', 'Peers', 'Valuation', 'Ownership', 'Filings', 'ESG', 'Governance', 'Intelligence', 'Structure'] },
      { id: 'sector', icon: IconSector, label: 'Sector', path: '/sector', shortcut: '4', subItems: ['Overview', 'Heatmap', 'Rotation'] },
    ],
  },
  {
    id: 'investment',
    label: 'Investment',
    items: [
      { id: 'fi', icon: IconFixedIncome, label: 'Fixed Inc', path: '/fi', shortcut: '5', subItems: ['Curves', 'Spreads', 'Issuance', 'Intelligence'] },
      { id: 'portfolio', icon: IconPortfolio, label: 'Portfolio', path: '/portfolio', shortcut: '6', subItems: ['Holdings', 'Attribution', 'Rebalance'] },
      { id: 'risk', icon: IconRisk, label: 'Risk', path: '/risk', shortcut: '7', subItems: ['VaR', 'Stress Test', 'Exposure'] },
      { id: 'adviser', icon: IconAdviser, label: 'Adviser', path: '/adviser', shortcut: 'A', subItems: ['Chat', 'What-If', 'Recommendations'] },
    ],
  },
  {
    id: 'macro',
    label: 'Macro',
    items: [
      { id: 'macro', icon: IconMacro, label: 'Macro', path: '/macro', shortcut: '8', subItems: ['Indicators', 'Yield Curve', 'Central Banks', 'Calendar'] },
      { id: 'global', icon: IconGlobal, label: 'Global', path: '/global', shortcut: '9', subItems: ['Markets', 'FX', 'Commodities', 'Countries', 'Political'] },
    ],
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    items: [
      { id: 'news', icon: IconNews, label: 'News', path: '/news', shortcut: '0', subItems: ['Feed', 'Trending', 'Saved'] },
      { id: 'research', icon: IconResearch, label: 'Research', path: '/research', shortcut: 'Q', subItems: ['Reports', 'Estimates', 'Transcripts', 'Anomalies', 'Search', 'Thesis', 'Analyst Q&A', 'Themes', 'Model Builder'] },
      { id: 'flows', icon: IconFlows, label: 'Flows', path: '/flows', shortcut: 'W', subItems: ['Fund Flows', 'Positioning', 'Sentiment'] },
      { id: 'smart-money', icon: IconSmartMoney, label: 'Smart $', path: '/smart-money', shortcut: 'T', subItems: ['13F Managers', 'Insiders', 'Politicians'] },
    ],
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    items: [
      { id: 'watchlist', icon: IconWatchlist, label: 'Watchlist', path: '/watchlist', shortcut: 'E', subItems: ['Lists', 'Movers', 'Alerts'] },
      { id: 'alerts', icon: IconAlerts, label: 'Alerts', path: '/alerts', shortcut: 'R', subItems: ['Active', 'History', 'Create'] },
      { id: 'dashboard', icon: IconDashboard, label: 'Dashboard', path: '/dashboard', shortcut: 'D', subItems: ['Custom Layout', 'Panels'] },
    ],
  },
];

const SETTINGS_ITEM: NavItemDef = {
  id: 'settings',
  icon: IconSettings,
  label: 'Settings',
  path: '/settings',
  shortcut: 'S',
  subItems: ['General', 'Display', 'Data', 'Shortcuts'],
};

/* ── Styles ───────────────────────────────────────────────── */

const RAIL_WIDTH = 56;
const ITEM_HEIGHT = 48;

const styles = {
  rail: {
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
    width: RAIL_WIDTH,
    minWidth: RAIL_WIDTH,
    background: 'var(--color-surface-base)',
    borderRight: '1px solid var(--color-surface-border)',
    overflowY: 'auto' as const,
    overflowX: 'hidden' as const,
    paddingTop: 4,
    paddingBottom: 4,
  },
  separator: {
    height: 1,
    margin: '4px 16px',
    background: 'var(--color-surface-border-strong)',
    flexShrink: 0,
  },
  spacer: {
    flex: 1,
    minHeight: 8,
  },
  navButton: (isActive: boolean, isHovered: boolean) => ({
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    width: '100%',
    height: ITEM_HEIGHT,
    border: 'none',
    cursor: 'pointer',
    position: 'relative' as const,
    padding: 0,
    gap: 2,
    transition: 'background 120ms ease, color 120ms ease',
    background: isActive
      ? 'var(--accent-glow)'
      : isHovered
        ? 'var(--color-surface-overlay)'
        : 'transparent',
    color: isActive
      ? 'var(--color-accent-primary)'
      : isHovered
        ? 'var(--color-text-secondary)'
        : 'var(--color-text-tertiary)',
    borderLeft: isActive ? '2px solid var(--color-accent-primary)' : '2px solid transparent',
    boxShadow: isActive ? 'inset 4px 0 12px -4px rgba(59, 130, 246, 0.2)' : 'none',
  }),
  iconContainer: {
    display: 'flex',
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    width: 20,
    height: 20,
  },
  label: {
    fontFamily: 'var(--font-ui)',
    fontSize: 9,
    lineHeight: 1,
    letterSpacing: '0.01em',
    whiteSpace: 'nowrap' as const,
    userSelect: 'none' as const,
  },
  shortcutBadge: {
    position: 'absolute' as const,
    top: 3,
    right: 4,
    fontFamily: 'var(--font-data)',
    fontSize: 8,
    lineHeight: 1,
    color: 'var(--color-text-tertiary)',
    opacity: 0.5,
  },
  flyout: {
    position: 'fixed' as const,
    left: RAIL_WIDTH + 4,
    zIndex: 300,
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 4,
    boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
    padding: '8px 12px',
    minWidth: 140,
    // Was 'none' -- made the flyout purely decorative, so its "links" could
    // never be clicked no matter how carefully the mouse was moved onto
    // them. Combined with the 4px left gap below and mouseleave firing the
    // instant the cursor left the nav button, the flyout was unreachable.
    pointerEvents: 'auto' as const,
  },
  flyoutSubClickable: {
    cursor: 'pointer' as const,
    borderRadius: 3,
    margin: '0 -6px',
    padding: '1px 6px',
    transition: 'background 100ms ease, color 100ms ease',
  },
  flyoutTitle: {
    fontFamily: 'var(--font-ui)',
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    marginBottom: 4,
  },
  flyoutGroup: {
    fontFamily: 'var(--font-ui)',
    fontSize: 9,
    color: 'var(--color-text-tertiary)',
    marginBottom: 2,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  flyoutSub: {
    fontFamily: 'var(--font-ui)',
    fontSize: 10,
    color: 'var(--color-text-secondary)',
    padding: '1px 0',
  },
  flyoutShortcut: {
    fontFamily: 'var(--font-data)',
    fontSize: 9,
    color: 'var(--color-text-tertiary)',
    marginTop: 6,
    borderTop: '1px solid var(--color-surface-border)',
    paddingTop: 4,
  },
} as const;

/* ── NavButton component ──────────────────────────────────── */

interface NavButtonProps {
  item: NavItemDef;
  isActive: boolean;
  groupLabel?: string;
  onClick: () => void;
}

function NavButton({ item, isActive, groupLabel, onClick }: NavButtonProps) {
  const [hovered, setHovered] = useState(false);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);
  // Bridges the gap between "cursor left the button" and "cursor reached the
  // flyout" (they're separate elements with a few pixels between them) --
  // closing was previously instant on mouseleave, so moving the mouse
  // toward the flyout to click a link always closed it first. A short
  // grace-period close, cancelled if the cursor lands on either the button
  // or the flyout before it fires, fixes that without needing exact
  // geometry/"safe polygon" math.
  const closeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelClose = useCallback(() => {
    if (closeTimeout.current) {
      clearTimeout(closeTimeout.current);
      closeTimeout.current = null;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    cancelClose();
    closeTimeout.current = setTimeout(() => {
      setHovered(false);
      setButtonRect(null);
    }, 150);
  }, [cancelClose]);

  useEffect(() => () => cancelClose(), [cancelClose]);

  const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
    cancelClose();
    setHovered(true);
    setButtonRect(e.currentTarget.getBoundingClientRect());
  }, [cancelClose]);

  const closeFlyout = useCallback(() => {
    cancelClose();
    setHovered(false);
    setButtonRect(null);
  }, [cancelClose]);

  const handleClick = useCallback(() => {
    closeFlyout();
    onClick();
  }, [closeFlyout, onClick]);

  const Icon = item.icon;

  return (
    <>
      <button
        style={styles.navButton(isActive, hovered)}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={scheduleClose}
        aria-label={item.label}
        aria-current={isActive ? 'page' : undefined}
        data-shortcut={item.shortcut}
      >
        <span style={styles.shortcutBadge}>{item.shortcut}</span>
        <span style={styles.iconContainer}>
          <Icon filled={isActive} />
        </span>
        <span style={styles.label}>{item.label}</span>
      </button>
      {hovered && buttonRect && (
        <FlyoutTooltip
          item={item}
          groupLabel={groupLabel}
          rect={buttonRect}
          onEnter={cancelClose}
          onLeave={scheduleClose}
          onNavigate={handleClick}
          onClose={closeFlyout}
        />
      )}
    </>
  );
}

/* ── FlyoutTooltip component ──────────────────────────────── */

interface FlyoutTooltipProps {
  item: NavItemDef;
  groupLabel?: string;
  rect: DOMRect;
  onEnter: () => void;
  onLeave: () => void;
  onNavigate: () => void;
  onClose: () => void;
}

// Real routes for specific sub-item labels, verified against
// src/router/index.tsx. Many of these pages already existed with real
// backend data wired up but had no navigation path to reach them at all
// (DATA_WIRING_AUDIT follow-up) -- this list is how they become reachable.
// A handful of remaining sub-item labels (e.g. Sector's "Rotation", Global's
// "FX", News's "Saved") have no backend data behind the concept yet and are
// intentionally left out here; they fall back to the parent section
// (item.path) via onNavigate, same as clicking the flyout title.
const SUBITEM_ROUTES: Record<string, Record<string, string>> = {
  home: { Dashboard: '/dashboard' },
  screener: { 'Fixed Income': '/screener/fi' },
  company: {
    Financials: '/company/financials',
    Peers: '/company/peers',
    Valuation: '/company/valuation',
    Ownership: '/company/ownership',
    Filings: '/company/filings',
    ESG: '/company/esg',
    Governance: '/company/governance',
    Intelligence: '/company/intelligence',
    Structure: '/company/complex-structure',
  },
  fi: { Curves: '/fi/treasuries', Spreads: '/fi/credit', Issuance: '/fi/issuance', Intelligence: '/fi/intelligence' },
  macro: { 'Yield Curve': '/macro/yield-curve', 'Central Banks': '/macro/central-banks', Calendar: '/macro/calendar' },
  global: { Commodities: '/global/commodities', Countries: '/global/countries', Political: '/global/political' },
  research: {
    Reports: '/research/primers',
    Estimates: '/research/estimates',
    Transcripts: '/research/transcripts',
    Anomalies: '/research/anomalies',
    Search: '/research/search',
    Thesis: '/research/thesis',
    'Analyst Q&A': '/research/qa',
    Themes: '/research/themes',
    'Model Builder': '/research/model-builder',
  },
  'smart-money': { Politicians: '/smart-money/politicians' },
  watchlist: { Alerts: '/alerts' },
};

function FlyoutTooltip({ item, groupLabel, rect, onEnter, onLeave, onNavigate, onClose }: FlyoutTooltipProps) {
  const navigate = useNavigate();
  const top = Math.max(4, rect.top);
  const [hoveredSub, setHoveredSub] = useState<string | null>(null);

  return (
    <div style={{ ...styles.flyout, top }} onMouseEnter={onEnter} onMouseLeave={onLeave}>
      {groupLabel && <div style={styles.flyoutGroup}>{groupLabel}</div>}
      <div
        style={{ ...styles.flyoutTitle, cursor: 'pointer' }}
        onClick={onNavigate}
      >
        {item.label}
      </div>
      {item.subItems && item.subItems.length > 0 && (
        <div style={{ marginTop: 2 }}>
          {/* Most sub-item labels are illustrative (no dedicated route per
              label -- e.g. Company's "Profile"/"Peers") and fall back to
              navigating the parent section, same as the flyout title. A few
              (SUBITEM_ROUTES above) map to a real distinct page. */}
          {item.subItems.map((sub) => (
            <div
              key={sub}
              style={{
                ...styles.flyoutSub,
                ...styles.flyoutSubClickable,
                background: hoveredSub === sub ? 'var(--color-surface-overlay)' : 'transparent',
                color: hoveredSub === sub ? 'var(--color-text-primary)' : styles.flyoutSub.color,
              }}
              onClick={() => {
                const route = SUBITEM_ROUTES[item.id]?.[sub];
                if (route) {
                  onClose();
                  navigate(route);
                } else {
                  onNavigate();
                }
              }}
              onMouseEnter={() => setHoveredSub(sub)}
              onMouseLeave={() => setHoveredSub((cur) => (cur === sub ? null : cur))}
            >
              {sub}
            </div>
          ))}
        </div>
      )}
      <div style={styles.flyoutShortcut}>
        Shortcut: {item.shortcut}
      </div>
    </div>
  );
}

/* ── Separator ────────────────────────────────────────────── */

function Separator() {
  return <div style={styles.separator} />;
}

/* ── NavRail ──────────────────────────────────────────────── */

export function NavRail() {
  const location = useLocation();
  const navigate = useNavigate();

  const isItemActive = useCallback(
    (path: string) =>
      location.pathname === path ||
      (path !== '/' && location.pathname.startsWith(path)),
    [location.pathname],
  );

  // Keyboard shortcut handler
  useEffect(() => {
    const allItems = [
      ...NAV_GROUPS.flatMap((g) => g.items),
      SETTINGS_ITEM,
    ];

    const handler = (e: KeyboardEvent) => {
      // Only fire when no modifier keys and no input is focused
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if ((e.target as HTMLElement).isContentEditable) return;

      const key = e.key.toUpperCase();
      const match = allItems.find((item) => item.shortcut === key);
      if (match) {
        e.preventDefault();
        navigate(match.path);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);

  return (
    <nav style={styles.rail} aria-label="Main navigation">
      {NAV_GROUPS.map((group, gi) => (
        <div key={group.id}>
          {gi > 0 && <Separator />}
          {group.items.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              isActive={isItemActive(item.path)}
              groupLabel={group.label}
              onClick={() => navigate(item.path)}
            />
          ))}
        </div>
      ))}

      <div style={styles.spacer} />
      <Separator />
      <NavButton
        item={SETTINGS_ITEM}
        isActive={isItemActive(SETTINGS_ITEM.path)}
        onClick={() => navigate(SETTINGS_ITEM.path)}
      />
    </nav>
  );
}
