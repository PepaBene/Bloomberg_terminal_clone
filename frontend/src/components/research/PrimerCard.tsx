import type { CSSProperties } from 'react';

export interface PrimerData {
  id: string;
  ticker: string;
  company: string;
  generatedAt: string;
  summary: string;
  bullCase: string;
  bearCase: string;
  targetPrice?: number;
  currentPrice?: number;
  qualityScore?: number;
}

export interface PrimerCardProps {
  primer: PrimerData;
  onOpen?: (id: string) => void;
}

function fmtDate(str: string): string {
  return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function uptodePct(target?: number, current?: number): string | null {
  if (target == null || current == null || current === 0) return null;
  const pct = ((target - current) / current) * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
}

export function PrimerCard({ primer, onOpen }: PrimerCardProps) {
  const upside = uptodePct(primer.targetPrice, primer.currentPrice);
  const upsideColor = upside
    ? upside.startsWith('+')
      ? 'var(--color-signal-positive)'
      : 'var(--color-signal-negative)'
    : 'var(--color-text-secondary)';

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    transition: 'border-color var(--transition-fast)',
  };

  return (
    <div className="animate-in" style={cardStyle}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            {primer.company}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              color: 'var(--color-accent-primary)',
              background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-sm)',
            }}>
              {primer.ticker}
            </span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              {fmtDate(primer.generatedAt)}
            </span>
          </div>
        </div>
        {primer.qualityScore != null && (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: primer.qualityScore >= 70
              ? 'var(--color-quality-5)'
              : primer.qualityScore >= 50
              ? 'var(--color-quality-3)'
              : 'var(--color-quality-1)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {primer.qualityScore}
          </span>
        )}
      </div>

      {/* Summary */}
      <p style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text-secondary)',
        margin: 0,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 3,
        WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'],
        lineHeight: 1.5,
      }}>
        {primer.summary}
      </p>

      {/* Bull / Bear */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
        <div style={{
          background: 'color-mix(in srgb, var(--color-signal-positive) 8%, transparent)',
          borderRadius: 'var(--radius-sm)',
          padding: 'var(--space-2)',
          borderLeft: '2px solid var(--color-signal-positive)',
        }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>↑ BULL</span>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', margin: '2px 0 0', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'] }}>
            {primer.bullCase}
          </p>
        </div>
        <div style={{
          background: 'color-mix(in srgb, var(--color-signal-negative) 8%, transparent)',
          borderRadius: 'var(--radius-sm)',
          padding: 'var(--space-2)',
          borderLeft: '2px solid var(--color-signal-negative)',
        }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)', fontWeight: 600 }}>↓ BEAR</span>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', margin: '2px 0 0', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'] }}>
            {primer.bearCase}
          </p>
        </div>
      </div>

      {/* Footer: target price + action */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--color-surface-border)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-2)' }}>
          {primer.currentPrice != null && (
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>
              ${primer.currentPrice.toFixed(2)}
            </span>
          )}
          {primer.targetPrice != null && (
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', fontVariantNumeric: 'tabular-nums' }}>
              → ${primer.targetPrice.toFixed(2)}
            </span>
          )}
          {upside != null && (
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: upsideColor, fontVariantNumeric: 'tabular-nums' }}>
              {upside}
            </span>
          )}
        </div>
        {onOpen && (
          <button
            type="button"
            onClick={() => onOpen(primer.id)}
            style={{
              background: 'var(--color-accent-primary)',
              color: 'var(--color-text-inverse)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              padding: '3px 10px',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Open Report
          </button>
        )}
      </div>
    </div>
  );
}

export default PrimerCard;
