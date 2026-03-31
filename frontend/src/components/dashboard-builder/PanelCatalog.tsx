import { useState } from 'react';
import type { CSSProperties } from 'react';

interface PanelType {
  type: string;
  name: string;
  description: string;
  icon: string;
  group: string;
}

const PANEL_TYPES: PanelType[] = [
  // Market Data
  { type: 'CompanyOverview', name: 'Company Overview', description: 'Key facts, sector, description and identifiers', icon: '🏢', group: 'Market Data' },
  { type: 'PriceChart', name: 'Price Chart', description: 'Interactive OHLCV candlestick and line chart', icon: '📈', group: 'Market Data' },
  { type: 'Fundamentals', name: 'Fundamentals', description: 'Income statement, balance sheet, cash flow', icon: '📊', group: 'Market Data' },
  { type: 'Screener', name: 'Screener', description: 'Multi-factor security screener with filters', icon: '🔍', group: 'Market Data' },
  { type: 'Watchlist', name: 'Watchlist', description: 'Monitor a list of securities in real time', icon: '👁', group: 'Market Data' },
  // Analytics
  { type: 'SectorHeatmap', name: 'Sector Heatmap', description: 'Heatmap of sector and industry performance', icon: '🟦', group: 'Analytics' },
  { type: 'Risk', name: 'Risk', description: 'VaR, drawdown, volatility and Greeks', icon: '⚠️', group: 'Analytics' },
  { type: 'Quant', name: 'Quant', description: 'Factor analysis and backtesting tools', icon: '🧮', group: 'Analytics' },
  { type: 'Macro', name: 'Macro', description: 'Economic indicators, yield curves, FX', icon: '🌍', group: 'Analytics' },
  { type: 'FIDashboard', name: 'FI Dashboard', description: 'Fixed income — duration, spreads, curves', icon: '📉', group: 'Analytics' },
  // Intelligence
  { type: 'News', name: 'News', description: 'Real-time news feed with sentiment tags', icon: '📰', group: 'Intelligence' },
  { type: 'Alerts', name: 'Alerts', description: 'Price, signal and condition alert manager', icon: '🔔', group: 'Intelligence' },
  { type: 'Research', name: 'Research', description: 'Analyst reports and recommendation history', icon: '📋', group: 'Intelligence' },
  // Portfolio
  { type: 'Portfolio', name: 'Portfolio', description: 'Holdings, attribution and performance', icon: '💼', group: 'Portfolio' },
];

const GROUPS = ['Market Data', 'Analytics', 'Intelligence', 'Portfolio'];

interface PanelCatalogProps {
  open: boolean;
  onClose: () => void;
  onAdd: (panelType: string) => void;
}

function PanelCatalog({ open, onClose, onAdd }: PanelCatalogProps) {
  const [hoveredType, setHoveredType] = useState<string | null>(null);

  const backdropStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    zIndex: 1000,
    opacity: open ? 1 : 0,
    pointerEvents: open ? 'auto' : 'none',
    transition: 'opacity var(--transition-normal)',
  };

  const panelStyle: CSSProperties = {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    width: 400,
    background: 'var(--color-surface-base)',
    borderLeft: '1px solid var(--color-surface-border-strong)',
    zIndex: 1001,
    display: 'flex',
    flexDirection: 'column',
    transform: open ? 'translateX(0)' : 'translateX(100%)',
    transition: 'transform var(--transition-normal)',
    boxShadow: 'var(--shadow-float)',
  };

  const headerStyle: CSSProperties = {
    padding: 'var(--space-4)',
    borderBottom: '1px solid var(--color-surface-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-md)',
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    margin: 0,
  };

  const closeButtonStyle: CSSProperties = {
    background: 'none',
    border: 'none',
    color: 'var(--color-text-tertiary)',
    cursor: 'pointer',
    fontSize: 'var(--text-lg)',
    lineHeight: 1,
    padding: 'var(--space-1)',
    borderRadius: 'var(--radius-sm)',
    transition: 'color var(--transition-fast)',
  };

  const scrollAreaStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: 'var(--space-3)',
  };

  const groupHeaderStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    padding: 'var(--space-3) var(--space-2) var(--space-2)',
    margin: 0,
  };

  const cardStyle = (type: string): CSSProperties => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 'var(--space-3)',
    padding: 'var(--space-3)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-surface-border)',
    background: hoveredType === type
      ? 'var(--color-surface-raised)'
      : 'var(--color-surface-overlay)',
    cursor: 'pointer',
    marginBottom: 'var(--space-2)',
    transition: 'background var(--transition-fast), border-color var(--transition-fast)',
    borderColor: hoveredType === type
      ? 'var(--color-surface-border-strong)'
      : 'var(--color-surface-border)',
  });

  const iconStyle: CSSProperties = {
    fontSize: 20,
    lineHeight: 1,
    flexShrink: 0,
    marginTop: 1,
  };

  const cardTitleStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    margin: '0 0 var(--space-1)',
  };

  const cardDescStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    margin: 0,
    lineHeight: 1.4,
  };

  return (
    <>
      <div style={backdropStyle} onClick={onClose} />
      <div style={panelStyle} className={open ? 'animate-in' : ''}>
        <div style={headerStyle}>
          <p style={titleStyle}>Add Panel</p>
          <button
            style={closeButtonStyle}
            onClick={onClose}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
          >
            ✕
          </button>
        </div>

        <div style={scrollAreaStyle}>
          {GROUPS.map(group => {
            const items = PANEL_TYPES.filter(p => p.group === group);
            return (
              <div key={group}>
                <p style={groupHeaderStyle}>{group}</p>
                {items.map(panel => (
                  <div
                    key={panel.type}
                    style={cardStyle(panel.type)}
                    onClick={() => { onAdd(panel.type); onClose(); }}
                    onMouseEnter={() => setHoveredType(panel.type)}
                    onMouseLeave={() => setHoveredType(null)}
                  >
                    <span style={iconStyle}>{panel.icon}</span>
                    <div>
                      <p style={cardTitleStyle}>{panel.name}</p>
                      <p style={cardDescStyle}>{panel.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

export default PanelCatalog;
