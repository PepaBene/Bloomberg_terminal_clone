import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '@/api/client';
import { SignalBadge } from '@/components/ui/SignalBadge';

export interface PreTradeTrade {
  ticker: string;
  direction: 'BUY' | 'SELL';
  shares: number;
  price: number;
}

export interface PreTradeCheckDialogProps {
  open: boolean;
  trade: PreTradeTrade | null;
  portfolioId: string;
  onClose: () => void;
  onConfirm: () => void;
}

interface PreTradeResult {
  weightImpact: number;
  varImpact: number;
  complianceChecks: { rule: string; status: 'Pass' | 'Warning' | 'Breach'; detail: string }[];
}

function statusColor(status: 'Pass' | 'Warning' | 'Breach'): string {
  switch (status) {
    case 'Pass': return 'var(--color-signal-positive)';
    case 'Warning': return 'var(--color-signal-warning)';
    case 'Breach': return 'var(--color-signal-negative)';
  }
}

function statusIcon(status: 'Pass' | 'Warning' | 'Breach'): string {
  switch (status) {
    case 'Pass': return '✓';
    case 'Warning': return '⚠';
    case 'Breach': return '✗';
  }
}

export function PreTradeCheckDialog({
  open,
  trade,
  portfolioId,
  onClose,
  onConfirm,
}: PreTradeCheckDialogProps) {
  const [result, setResult] = useState<PreTradeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !trade) return;
    setLoading(true);
    setResult(null);
    setError(null);
    api
      .post(`/v1/portfolios/${portfolioId}/pre-trade-check`, trade)
      .then((data: unknown) => setResult(data as PreTradeResult))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Check failed'))
      .finally(() => setLoading(false));
  }, [open, trade, portfolioId]);

  if (!open || !trade) return null;

  const hasBreaches = result?.complianceChecks.some((c) => c.status === 'Breach') ?? false;

  const overlayStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const dialogStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-5)',
    width: '480px',
    maxWidth: '95vw',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-4)',
  };

  const sectionTitleStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: 'var(--space-2)',
  };

  const impactRowStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 0',
    borderBottom: '1px solid var(--color-surface-border)',
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        className="animate-in"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            Pre-Trade Check
          </span>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-tertiary)', cursor: 'pointer', fontSize: 'var(--text-base)' }}>
            ✕
          </button>
        </div>

        {/* Trade summary */}
        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-raised)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-surface-border)' }}>
          <SignalBadge
            label={trade.direction}
            variant={trade.direction === 'BUY' ? 'positive' : 'negative'}
          />
          <span style={{ fontFamily: 'var(--font-data)', fontWeight: 700, color: 'var(--color-accent-primary)' }}>
            {trade.ticker}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}>
            {trade.shares.toLocaleString()} sh @ ${trade.price.toFixed(2)}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)', marginLeft: 'auto' }}>
            ${(trade.shares * trade.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
            Running checks...
          </div>
        )}

        {error && (
          <div style={{ color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)' }}>
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Impact metrics */}
            <div>
              <div style={sectionTitleStyle}>Impact Analysis</div>
              <div style={impactRowStyle}>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>Weight Impact</span>
                <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-sm)', color: result.weightImpact > 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                  {result.weightImpact >= 0 ? '+' : ''}{result.weightImpact.toFixed(2)}%
                </span>
              </div>
              <div style={impactRowStyle}>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>VaR Impact</span>
                <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-sm)', color: result.varImpact > 0 ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)' }}>
                  {result.varImpact >= 0 ? '+' : ''}{result.varImpact.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Compliance checks */}
            <div>
              <div style={sectionTitleStyle}>Compliance Checks</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {result.complianceChecks.map((check, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', padding: '4px 0' }}>
                    <span style={{ color: statusColor(check.status), fontSize: '14px', lineHeight: 1, width: '16px', textAlign: 'center' }}>
                      {statusIcon(check.status)}
                    </span>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', flex: 1 }}>
                      {check.rule}
                    </span>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: statusColor(check.status) }}>
                      {check.detail}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end', borderTop: '1px solid var(--color-surface-border)', paddingTop: 'var(--space-3)' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 16px',
              background: 'transparent',
              color: 'var(--color-text-tertiary)',
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading || hasBreaches}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '6px 20px',
              background: hasBreaches ? 'var(--color-signal-negative)' : 'var(--color-accent-primary)',
              color: 'var(--color-surface-void)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: loading || hasBreaches ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
            }}
          >
            {hasBreaches ? 'Breach — Blocked' : 'Confirm Trade'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PreTradeCheckDialog;
