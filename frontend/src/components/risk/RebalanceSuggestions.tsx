import type { CSSProperties } from 'react';
import { SignalBadge } from '@/components/ui/SignalBadge';

export interface RebalanceTrade {
  ticker: string;
  action: 'BUY' | 'SELL';
  shares: number;
  dollarAmount: number;
  reason: string;
}

export interface RebalanceSuggestionsProps {
  trades: RebalanceTrade[];
  onExecute?: (trade: RebalanceTrade) => void;
}

export function RebalanceSuggestions({ trades, onExecute }: RebalanceSuggestionsProps) {
  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: 'var(--space-2)',
    borderBottom: '1px solid var(--color-surface-border)',
  };

  const tableHeaderStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '50px 70px 80px 100px 1fr 90px',
    gap: 'var(--space-2)',
    padding: '4px 8px',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    borderBottom: '1px solid var(--color-surface-border)',
  };

  const rowStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '50px 70px 80px 100px 1fr 90px',
    gap: 'var(--space-2)',
    alignItems: 'center',
    padding: '6px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    transition: 'background 0.1s',
  };

  const handleExecuteAll = () => {
    if (onExecute) {
      trades.forEach((t) => onExecute(t));
    }
  };

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={headerStyle}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {trades.length} suggested trade{trades.length !== 1 ? 's' : ''}
        </span>
        {onExecute && trades.length > 0 && (
          <button
            type="button"
            onClick={handleExecuteAll}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              padding: '4px 12px',
              height: '26px',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-surface-void)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            Execute All
          </button>
        )}
      </div>

      <div style={tableHeaderStyle}>
        <span>Action</span>
        <span>Ticker</span>
        <span style={{ textAlign: 'right' }}>Shares</span>
        <span style={{ textAlign: 'right' }}>Amount</span>
        <span>Reason</span>
        <span />
      </div>

      {trades.map((trade, i) => (
        <div
          key={i}
          style={rowStyle}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.background = 'transparent';
          }}
        >
          <SignalBadge
            label={trade.action}
            variant={trade.action === 'BUY' ? 'positive' : 'negative'}
          />

          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontWeight: 700,
              fontSize: 'var(--text-sm)',
              color: 'var(--color-accent-primary)',
            }}
          >
            {trade.ticker}
          </span>

          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-primary)',
              textAlign: 'right',
            }}
          >
            {trade.shares.toLocaleString()}
          </span>

          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              fontSize: 'var(--text-xs)',
              color: trade.action === 'BUY' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)',
              textAlign: 'right',
            }}
          >
            ${Math.abs(trade.dollarAmount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>

          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-secondary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {trade.reason}
          </span>

          {onExecute && (
            <button
              type="button"
              onClick={() => onExecute(trade)}
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                padding: '3px 8px',
                height: '22px',
                background: 'transparent',
                color: 'var(--color-accent-primary)',
                border: '1px solid var(--color-accent-primary)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Execute
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export default RebalanceSuggestions;
