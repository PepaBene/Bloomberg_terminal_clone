// ---------------------------------------------------------------------------
// News View — News Feed with Entity Tagging, Sentiment Scores, Filtering
// ---------------------------------------------------------------------------
import { SentimentGauge } from '@/components/intelligence';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
function sentimentColor(s: number): string {
  if (s > 0.3) return 'var(--color-signal-positive)';
  if (s < -0.3) return 'var(--color-signal-negative)';
  return 'var(--color-text-secondary)';
}

const filters = ['All', 'Earnings', 'M&A', 'Macro', 'Regulatory', 'Insider'];

const newsItems = [
  { id: 1, time: '11:42', headline: 'NVIDIA reports record Q4 data center revenue of $18.4B, beating estimates', source: 'Bloomberg', entities: ['NVDA'], sentiment: 0.85 },
  { id: 2, time: '11:28', headline: 'Fed Chair Powell signals patience on rate cuts amid sticky inflation', source: 'Reuters', entities: ['FED', 'MACRO'], sentiment: -0.42 },
  { id: 3, time: '10:55', headline: 'Apple exploring strategic acquisition of AI startup for $2B', source: 'WSJ', entities: ['AAPL'], sentiment: 0.55 },
  { id: 4, time: '10:32', headline: 'JPMorgan downgrades consumer discretionary sector to underweight', source: 'CNBC', entities: ['JPM', 'XLY'], sentiment: -0.38 },
  { id: 5, time: '09:48', headline: 'European Central Bank holds rates steady, signals June cut possible', source: 'FT', entities: ['ECB', 'MACRO'], sentiment: 0.22 },
  { id: 6, time: '09:15', headline: 'Tesla recalls 125,000 vehicles over steering column issue', source: 'Bloomberg', entities: ['TSLA'], sentiment: -0.65 },
  { id: 7, time: '08:45', headline: 'Pfizer insider purchase: CEO buys $2.1M in shares on open market', source: 'SEC Filing', entities: ['PFE'], sentiment: 0.45 },
  { id: 8, time: '08:30', headline: 'Initial jobless claims rise to 225K, above 212K forecast', source: 'BLS', entities: ['MACRO'], sentiment: -0.25 },
];

export default function NewsView() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>News Feed</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
          {filters.map((f) => (
            <span key={f} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: f === 'All' ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)', color: f === 'All' ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)', cursor: 'pointer' }}>{f}</span>
          ))}
        </div>
      </div>
      {/* Market-wide Sentiment Gauge */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        <div style={panelStyle}>
          <SentimentGauge value={0.32} momentum="IMPROVING" label="Market Sentiment" />
        </div>
        <div style={panelStyle}>
          <SentimentGauge value={0.85} momentum="STABLE" label="NVDA" />
        </div>
        <div style={panelStyle}>
          <SentimentGauge value={-0.42} momentum="DECLINING" label="Fed / Macro" />
        </div>
        <div style={panelStyle}>
          <SentimentGauge value={-0.65} momentum="DECLINING" label="TSLA" />
        </div>
      </div>

      <div style={panelStyle}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {newsItems.map((n) => (
            <div key={n.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--color-surface-border)', display: 'grid', gridTemplateColumns: '50px 1fr 80px 60px', gap: '12px', alignItems: 'start' }}>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>{n.time}</span>
              <div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>{n.headline}</div>
                <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)' }}>{n.source}</span>
                  {n.entities.map((e) => (
                    <span key={e} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', background: 'var(--color-surface-overlay)', padding: '1px 4px', borderRadius: '2px' }}>{e}</span>
                  ))}
                </div>
              </div>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', color: sentimentColor(n.sentiment), fontWeight: 500 }}>{n.sentiment > 0 ? '+' : ''}{n.sentiment.toFixed(2)}</span>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', textAlign: 'right', color: sentimentColor(n.sentiment) }}>
                {n.sentiment > 0.3 ? 'Bullish' : n.sentiment < -0.3 ? 'Bearish' : 'Neutral'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
