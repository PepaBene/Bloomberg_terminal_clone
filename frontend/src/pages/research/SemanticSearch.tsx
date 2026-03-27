// ---------------------------------------------------------------------------
// Semantic Search — Search Interface with Results and Filters
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

const query = 'companies with declining margins and increasing leverage in technology sector';
const resultCount = 42;

const filters = ['All Sources', '10-K/10-Q', 'Earnings Calls', 'News', 'Research', 'Credit Reports'];

const results = [
  { rank: 1, title: 'Intel Corp (INTC) — 10-K FY2025', snippet: '...gross margin declined to 41.5% from 45.2% in the prior year, driven by competitive pressure in data center and foundry ramp costs. Total debt increased to $52.8B...', relevance: 0.95, date: '2026-02-28', source: '10-K' },
  { rank: 2, title: 'Qualcomm (QCOM) — Q4 2025 Earnings Call', snippet: '...operating margin compression of 280 bps year-over-year as we invested heavily in automotive and IoT diversification. Net debt position increased by $2.4B...', relevance: 0.88, date: '2025-11-05', source: 'Earnings Call' },
  { rank: 3, title: 'AMD — 10-Q Q1 2026', snippet: '...EBITDA margin of 22.8% versus 26.1% in Q1 2025 reflecting pricing pressure in consumer GPU segment. Revolving credit facility drawn by $1.2B...', relevance: 0.84, date: '2026-01-31', source: '10-Q' },
  { rank: 4, title: 'Texas Instruments (TXN) — Credit Research Note', snippet: '...leverage ratio increased to 2.1x from 1.4x following the $4B capacity expansion program. Operating margins expected to compress 150-200bps...', relevance: 0.81, date: '2026-03-15', source: 'Research' },
  { rank: 5, title: 'Micron Technology (MU) — 10-K FY2025', snippet: '...net margin declined to 8.2% from 12.5% as memory pricing weakness persisted through H1. Long-term debt increased $3.5B to fund fab expansion...', relevance: 0.78, date: '2025-12-20', source: '10-K' },
];

export default function SemanticSearch() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Semantic Search</h1>
      </div>
      {/* Search Box */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <div style={{ flex: 1, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', background: 'var(--color-surface-overlay)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', padding: '8px 12px' }}>{query}</div>
        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-inverse)', background: 'var(--color-accent-primary)', padding: '6px 16px', borderRadius: '3px', cursor: 'pointer' }}>Search</div>
      </div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: 'var(--panel-gap)' }}>
        {filters.map((f) => (
          <span key={f} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: f === 'All Sources' ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)', color: f === 'All Sources' ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)', cursor: 'pointer' }}>{f}</span>
        ))}
        <span style={{ marginLeft: 'auto', ...labelStyle }}>{resultCount} results</span>
      </div>
      {/* Results */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {results.map((r) => (
          <div key={r.rank} style={panelStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'baseline' }}>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>#{r.rank}</span>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{r.title}</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>Relevance: {(r.relevance * 100).toFixed(0)}%</span>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{r.date}</span>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', background: 'var(--color-surface-overlay)', padding: '1px 4px', borderRadius: '2px' }}>{r.source}</span>
              </div>
            </div>
            <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.5, margin: 0 }}>{r.snippet}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
