import { useLocation, useNavigate } from 'react-router-dom';
import clsx from 'clsx';

interface NavItem {
  icon: string;
  label: string;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { icon: '\u{1F3E0}', label: 'Home', path: '/' },
  { icon: '\u{1F50D}', label: 'Screener', path: '/screener' },
  { icon: '\u{1F3E2}', label: 'Company', path: '/company' },
  { icon: '\u{1F4CA}', label: 'Sector', path: '/sector' },
  { icon: '\u{1F4B0}', label: 'Fixed Inc', path: '/fi' },
  { icon: '\u{1F4C1}', label: 'Portfolio', path: '/portfolio' },
  { icon: '\u2696\uFE0F', label: 'Risk', path: '/risk' },
  { icon: '\u{1F30D}', label: 'Macro', path: '/macro' },
  { icon: '\u{1F310}', label: 'Global', path: '/global' },
  { icon: '\u{1F4F0}', label: 'News', path: '/news' },
  { icon: '\u{1F52C}', label: 'Research', path: '/research' },
  { icon: '\u{1F4C8}', label: 'Flows', path: '/flows' },
  { icon: '\u2B50', label: 'Watchlist', path: '/watchlist' },
  { icon: '\uD83D\uDD14', label: 'Alerts', path: '/alerts' },
  { icon: '\u2699\uFE0F', label: 'Settings', path: '/settings' },
];

export function NavRail() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="flex flex-col h-full bg-surface-base border-r border-surface-border overflow-y-auto py-1">
      {NAV_ITEMS.map((item) => {
        const isActive = location.pathname === item.path ||
          (item.path !== '/' && location.pathname.startsWith(item.path));

        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={clsx(
              'flex flex-col items-center justify-center w-full h-12 text-xs gap-0.5 transition-colors relative',
              isActive
                ? 'text-accent-primary bg-surface-overlay'
                : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-overlay/50'
            )}
          >
            {isActive && (
              <div className="absolute left-0 top-1 bottom-1 w-0.5 bg-accent-primary rounded-r" />
            )}
            <span className="text-base">{item.icon}</span>
            <span className="font-ui text-[9px] leading-none">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
