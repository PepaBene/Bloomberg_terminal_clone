import type { CSSProperties } from 'react';

export interface SearchResult {
  id: string;
  ticker?: string;
  title: string;
  snippet: string;
  score: number;
  source: 'filing' | 'transcript' | 'primer' | 'news' | 'briefing';
  date: string;
}

export interface SearchResultCardProps {
  result: SearchResult;
  onClick?: (id: string) => void;
}

const SOURCE_COLORS: Record<string, string> = {
  filing: 'var(--color-chart-3)',
  transcript: 'var(--color-chart-1)',
  primer: 'var(--color-color-signal-positive)',
  news: 'var(--color-chart-6)',
  briefing: 'var(--color-chart-4)',
};

const SOURCE_LABEL: Record<string, string> = {
  filing: 'Filing',
  transcript: 'Transcript',
  primer: 'Primer',
  news: 'News',
  briefing: 'Briefing',
};

function fmtDate(str: string): string {
  return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function SearchResultCard({ result, onClick }: SearchResultCardProps) {
  const sourceColor = SOURCE_COLORS[result.source] ?? 'var(--color-text-tertiary)';
  const scoreBarWidth = `${Math.round(result.score * 100)}%`;

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    cursor: onClick ? 'pointer' : 'default',
    transition: 'border-color var(--transition-fast)',
  };

  return (
    <div
      className="animate-in"
      style={cardStyle}
      onClick={() => onClick?.(result.id)}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {/* Top row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: sourceColor,
            background: `color-mix(in srgb, ${sourceColor} 12%, transparent)`,
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {SOURCE_LABEL[result.source]}
          </span>
          {result.ticker && (
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              color: 'var(--color-accent-primary)',
            }}>
              {result.ticker}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {/* Relevance bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              Relevance
            </span>
            <div style={{ width: 60, height: 4, background: 'var(--color-surface-overlay)', borderRadius: 2 }}>
              <div style={{ width: scoreBarWidth, height: '100%', background: 'var(--color-accent-primary)', borderRadius: 2 }} />
            </div>
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
              {Math.round(result.score * 100)}%
            </span>
          </div>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            {fmtDate(result.date)}
          </span>
        </div>
      </div>

      {/* Title */}
      <h4 style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        fontWeight: 600,
        color: 'var(--color-text-primary)',
        margin: 0,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {result.title}
      </h4>

      {/* Snippet */}
      <p style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-xs)',
        color: 'var(--color-text-secondary)',
        margin: 0,
        lineHeight: 1.5,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical' as CSSProperties['WebkitBoxOrient'],
      }}>
        {result.snippet}
      </p>
    </div>
  );
}

export default SearchResultCard;
