// ---------------------------------------------------------------------------
// News View — News Feed with Entity Tagging, Sentiment Scores, Filtering
//
// Wired to GET /v3/news/latest (news.py), a bare array of NewsArticleResponse:
//   { id, title, summary, source_name, publish_date, news_type, topics,
//     sentiment_score, sentiment_label, source_url, entities:[{entity_id,
//     mention_text, ...}] }
//
// The previous version read `n.headline / n.time / n.sentiment / n.category`
// (none of which exist on the schema) and called `n.sentiment.toFixed(2)` —
// which threw the instant any real article was returned (DATA_WIRING_AUDIT
// §3.7/§8.2). Field names are now mapped correctly and sentiment is null-safe.
// ---------------------------------------------------------------------------
import { useState, useMemo } from 'react';
import { SentimentGauge } from '@/components/intelligence';
import { EmptyState } from '@/components/feedback';
import { useNews } from '@/hooks';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
function sentimentColor(s: number): string {
  if (s > 0.3) return 'var(--color-signal-positive)';
  if (s < -0.3) return 'var(--color-signal-negative)';
  return 'var(--color-text-secondary)';
}

const filters = ['All', 'Earnings', 'M&A', 'Macro', 'Regulatory', 'Insider'];

interface NewsEntityDTO {
  entity_id: string;
  mention_text?: string | null;
  is_primary?: boolean;
}
interface NewsArticleDTO {
  id: string;
  title: string;
  summary?: string | null;
  source_name?: string | null;
  publish_date?: string | null;
  news_type?: string | null;
  topics?: string[] | null;
  sentiment_score?: number | null;
  sentiment_label?: string | null;
  entities?: NewsEntityDTO[] | null;
}

interface NewsRow {
  id: string;
  time: string;
  headline: string;
  source: string;
  entities: string[];
  sentiment: number | null;
  category: string;
}

function formatTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

export default function NewsView() {
  const { data: apiNews, isLoading, isError } = useNews() as {
    data: NewsArticleDTO[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const newsRows: NewsRow[] = useMemo(() => {
    const arr = Array.isArray(apiNews) ? apiNews : [];
    return arr.map((n) => ({
      id: String(n.id),
      time: formatTime(n.publish_date),
      headline: n.title,
      source: n.source_name ?? '—',
      entities: (n.entities ?? []).map((e) => e.mention_text || e.entity_id).slice(0, 4),
      sentiment: n.sentiment_score ?? null,
      category: n.news_type ?? '',
    }));
  }, [apiNews]);

  const [activeFilter, setActiveFilter] = useState('All');

  const filteredNews = useMemo(
    () =>
      activeFilter === 'All'
        ? newsRows
        : newsRows.filter((n) => n.category.toUpperCase().includes(activeFilter.toUpperCase())),
    [activeFilter, newsRows],
  );

  // Market sentiment = mean of the scored articles actually loaded (real, not
  // fabricated). Rendered only when at least one article carries a score.
  const marketSentiment = useMemo(() => {
    const scored = newsRows.map((n) => n.sentiment).filter((s): s is number => s != null);
    if (scored.length === 0) return null;
    return scored.reduce((a, b) => a + b, 0) / scored.length;
  }, [newsRows]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>News Feed</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
          {filters.map((f) => (
            <span
              key={f}
              onClick={() => setActiveFilter(f)}
              style={{
                fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px',
                background: f === activeFilter ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
                color: f === activeFilter ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
                cursor: 'pointer',
              }}
            >{f}</span>
          ))}
        </div>
      </div>

      {/* Market-wide Sentiment Gauge — computed from loaded articles */}
      {marketSentiment != null && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
          <div style={panelStyle}>
            <SentimentGauge value={marketSentiment} label={`Market Sentiment (${newsRows.length} articles)`} />
          </div>
        </div>
      )}

      <div style={panelStyle}>
        {isLoading ? (
          <EmptyState icon="⏳" title="Loading news…" />
        ) : isError ? (
          <EmptyState icon="⚠️" title="Failed to load news" description="Please try again later." />
        ) : filteredNews.length === 0 ? (
          <EmptyState
            icon="📰"
            title={newsRows.length === 0 ? 'No news available' : `No ${activeFilter} news`}
            description={
              newsRows.length === 0
                ? 'News ingestion requires a configured news source (FINNHUB_API_KEY).'
                : 'Try a different filter.'
            }
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {filteredNews.map((n) => (
              <div key={n.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--color-surface-border)', display: 'grid', gridTemplateColumns: '50px 1fr 80px 60px', gap: '12px', alignItems: 'start' }}>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>{n.time}</span>
                <div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>{n.headline}</div>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)' }}>{n.source}</span>
                    {n.entities.map((e, i) => (
                      <span key={`${n.id}-${i}`} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', background: 'var(--color-surface-overlay)', padding: '1px 4px', borderRadius: '2px' }}>{e}</span>
                    ))}
                  </div>
                </div>
                {n.sentiment != null ? (
                  <>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', color: sentimentColor(n.sentiment), fontWeight: 500 }}>{n.sentiment > 0 ? '+' : ''}{n.sentiment.toFixed(2)}</span>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', textAlign: 'right', color: sentimentColor(n.sentiment) }}>
                      {n.sentiment > 0.3 ? 'Bullish' : n.sentiment < -0.3 ? 'Bearish' : 'Neutral'}
                    </span>
                  </>
                ) : (
                  <>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', color: 'var(--color-text-tertiary)' }}>—</span>
                    <span />
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
