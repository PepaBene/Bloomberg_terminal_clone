import type { CSSProperties } from 'react';

export interface PortfolioHeaderProps {
  name: string;
  nav: number;
  dayChange: number;
  dayChangeDollar: number;
  inception: string;
  benchmark?: string;
  onEdit?: () => void;
}

function fmt(v: number, decimals = 2): string {
  return v.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtDollar(v: number): string {
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  if (abs >= 1_000_000) return `${sign}$${fmt(abs / 1_000_000)}M`;
  if (abs >= 1_000) return `${sign}$${fmt(abs / 1_000)}K`;
  return `${sign}$${fmt(abs)}`;
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-secondary)';
}

interface KPIItemProps {
  label: string;
  value: string;
  color?: string;
}

function KPIItem({ label, value, color }: KPIItemProps) {
  const itemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    padding: '0 var(--space-4)',
    borderRight: '1px solid var(--color-surface-border)',
  };
  return (
    <div style={itemStyle}>
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
          fontVariantNumeric: 'tabular-nums',
          color: color ?? 'var(--color-text-primary)',
        }}
      >
        {value}
      </span>
    </div>
  );
}

export function PortfolioHeader({
  name,
  nav,
  dayChange,
  dayChangeDollar,
  inception,
  benchmark,
  onEdit,
}: PortfolioHeaderProps) {
  const changeColor = signalColor(dayChange);
  const changeSign = dayChange >= 0 ? '+' : '';

  const rootStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--panel-padding)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  };

  const topRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 'var(--space-4)',
  };

  const nameBlockStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-1)',
  };

  const navBlockStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'baseline',
    gap: 'var(--space-3)',
  };

  const kpiStripStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'stretch',
    borderTop: '1px solid var(--color-surface-border)',
    paddingTop: 'var(--space-2)',
    gap: '0',
  };

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={topRowStyle}>
        <div style={nameBlockStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xl)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
              }}
            >
              {name}
            </span>
            {onEdit && (
              <button
                type="button"
                onClick={onEdit}
                style={{
                  background: 'none',
                  border: '1px solid var(--color-surface-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '2px 8px',
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  cursor: 'pointer',
                }}
              >
                Edit
              </button>
            )}
          </div>
          {benchmark && (
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-tertiary)',
              }}
            >
              vs {benchmark}
            </span>
          )}
        </div>

        <div style={navBlockStyle}>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xl)',
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--color-text-primary)',
            }}
          >
            ${nav.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-base)',
              fontVariantNumeric: 'tabular-nums',
              color: changeColor,
            }}
          >
            {changeSign}{fmt(dayChange)}%
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              fontVariantNumeric: 'tabular-nums',
              color: changeColor,
            }}
          >
            ({fmtDollar(dayChangeDollar)})
          </span>
        </div>
      </div>

      <div style={kpiStripStyle}>
        <KPIItem
          label="NAV"
          value={`$${nav.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
        />
        <KPIItem
          label="Day P&L"
          value={fmtDollar(dayChangeDollar)}
          color={changeColor}
        />
        <KPIItem
          label="Day Change"
          value={`${changeSign}${fmt(dayChange)}%`}
          color={changeColor}
        />
        <KPIItem
          label="Inception"
          value={inception}
        />
        {benchmark && (
          <KPIItem
            label="Benchmark"
            value={benchmark}
          />
        )}
      </div>
    </div>
  );
}

export default PortfolioHeader;
