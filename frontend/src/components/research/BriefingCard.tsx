import type { CSSProperties } from 'react';

export interface BriefingData {
  id: string;
  title: string;
  date: string;
  summary: string;
  marketSentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  highlights: string[];
}

export interface BriefingCardProps {
  briefing: BriefingData;
  onRead?: (id: string) => void;
}

const SENTIMENT_COLOR: Record<string, string> = {
  BULLISH: 'var(--color-signal-positive)',
  BEARISH: 'var(--color-signal-negative)',
  NEUTRAL: 'var(--color-signal-neutral)',
};

function fmtDate(str: string): string {
  return new Date(str).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function BriefingCard({ briefing, onRead }: BriefingCardProps) {
  const sentColor = SENTIMENT_COLOR[briefing.marketSentiment] ?? 'var(--color-text-secondary)';

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  return (
    <div className="animate-in" style={cardStyle}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ flex: 1 }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
            {fmtDate(briefing.date)}
          </span>
          <h3 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '2px 0 0' }}>
            {briefing.title}
          </h3>
        </div>
        <span style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 600,
          color: sentColor,
          background: `color-mix(in srgb, ${sentColor} 12%, transparent)`,
          padding: '2px 8px',
          borderRadius: 'var(--radius-sm)',
          whiteSpace: 'nowrap',
        }}>
          {briefing.marketSentiment}
        </span>
      </div>

      {/* Summary */}
      <p style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text-secondary)',
        margin: 0,
        lineHeight: 1.5,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'],
      }}>
        {briefing.summary}
      </p>

      {/* Highlights */}
      {briefing.highlights.length > 0 && (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {briefing.highlights.slice(0, 3).map((h, i) => (
            <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-1)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
              <span style={{ color: 'var(--color-accent-primary)', marginTop: '1px', flexShrink: 0 }}>•</span>
              {h}
            </li>
          ))}
        </ul>
      )}

      {/* CTA */}
      {onRead && (
        <div style={{ borderTop: '1px solid var(--color-surface-border)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
          <button
            type="button"
            onClick={() => onRead(briefing.id)}
            style={{
              background: 'none',
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '3px 10px',
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
            }}
          >
            Read Full Briefing →
          </button>
        </div>
      )}
    </div>
  );
}

export default BriefingCard;
