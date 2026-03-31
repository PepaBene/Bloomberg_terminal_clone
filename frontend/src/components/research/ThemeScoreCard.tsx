import type { CSSProperties } from 'react';

export interface ThemeData {
  id: string;
  name: string;
  description: string;
  score: number;
  momentum: number;
  relatedTickers: string[];
  lastUpdated: string;
}

export interface ThemeScoreCardProps {
  theme: ThemeData;
  onOpen?: (id: string) => void;
}

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--color-quality-5)';
  if (score >= 50) return 'var(--color-quality-3)';
  if (score >= 30) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

function momentumArrow(momentum: number): string {
  if (momentum > 0.05) return '↑';
  if (momentum < -0.05) return '↓';
  return '→';
}

function momentumColor(momentum: number): string {
  if (momentum > 0.05) return 'var(--color-signal-positive)';
  if (momentum < -0.05) return 'var(--color-signal-negative)';
  return 'var(--color-signal-neutral)';
}

function fmtDate(str: string): string {
  return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function ThemeScoreCard({ theme, onOpen }: ThemeScoreCardProps) {
  const sColor = scoreColor(theme.score);
  const mArrow = momentumArrow(theme.momentum);
  const mColor = momentumColor(theme.momentum);

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    cursor: onOpen ? 'pointer' : 'default',
  };

  return (
    <div
      className="animate-in"
      style={cardStyle}
      onClick={() => onOpen?.(theme.id)}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
            }}>
              {theme.name}
            </span>
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-base)', fontWeight: 700, color: mColor }}>
              {mArrow}
            </span>
          </div>
          <p style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            margin: '2px 0 0',
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'],
            lineHeight: 1.4,
          }}>
            {theme.description}
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px', flexShrink: 0 }}>
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xl)',
            fontWeight: 700,
            color: sColor,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {theme.score}
          </span>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            /100
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div style={{ height: 4, background: 'var(--color-surface-overlay)', borderRadius: 2 }}>
        <div style={{
          height: '100%',
          width: `${theme.score}%`,
          background: sColor,
          borderRadius: 2,
          transition: 'width var(--transition-normal)',
        }} />
      </div>

      {/* Footer: tickers + date */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
          {theme.relatedTickers.slice(0, 5).map(t => (
            <span key={t} style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              color: 'var(--color-text-secondary)',
              background: 'var(--color-surface-raised)',
              border: '1px solid var(--color-surface-border)',
              padding: '0 4px',
              borderRadius: 'var(--radius-sm)',
            }}>
              {t}
            </span>
          ))}
          {theme.relatedTickers.length > 5 && (
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              +{theme.relatedTickers.length - 5} more
            </span>
          )}
        </div>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>
          {fmtDate(theme.lastUpdated)}
        </span>
      </div>
    </div>
  );
}

export default ThemeScoreCard;
