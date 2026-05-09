// ---------------------------------------------------------------------------
// Semantic Search — Search Interface with Results and Filters
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

// F-008: page no longer pre-fills a semiconductor-focused query and 5
// hardcoded INTC/QCOM/AMD/TXN/MU "results" — those rendered as if they
// were a real semantic-search hit on whatever the user just typed.
const query = '';
const resultCount = 0;

const filters = ['All Sources', '10-K/10-Q', 'Earnings Calls', 'News', 'Research', 'Credit Reports'];

const results: { rank: number; title: string; snippet: string; relevance: number; date: string; source: string }[] = [];

export default function SemanticSearch() {
  const [searchQuery, setSearchQuery] = useState(query);
  const [searchResults, setSearchResults] = useState<typeof results | null>(null);
  const [activeFilter, setActiveFilter] = useState('All Sources');
  const [searching, setSearching] = useState(false);

  const displayResults = searchResults ?? results;
  const displayCount = searchResults?.length ?? resultCount;

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await api.post(RESEARCH.search.query, { query: searchQuery, filter: activeFilter });
      setSearchResults((res as any)?.results ?? []);
    } catch { setSearchResults(null); }
    setSearching(false);
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Semantic Search</h1>
      </div>
      {/* Search Box */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Search filings, transcripts, research..."
          style={{ flex: 1, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', background: 'var(--color-surface-overlay)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', padding: '8px 12px' }}
        />
        <button onClick={handleSearch} disabled={searching} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-inverse)', background: 'var(--color-accent-primary)', padding: '6px 16px', borderRadius: '3px', cursor: 'pointer', border: 'none' }}>
          {searching ? 'Searching…' : 'Search'}
        </button>
      </div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: 'var(--panel-gap)' }}>
        {filters.map((f) => (
          <span key={f} onClick={() => setActiveFilter(f)} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: f === activeFilter ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)', color: f === activeFilter ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)', cursor: 'pointer' }}>{f}</span>
        ))}
        <span style={{ marginLeft: 'auto', ...labelStyle }}>{displayCount} results</span>
      </div>
      {/* Results */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {displayResults.map((r) => (
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
