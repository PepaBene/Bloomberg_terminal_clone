// ---------------------------------------------------------------------------
// Custom Index Builder — Build & Manage Custom Indices / Benchmarks
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useBenchmarks, useCreateBenchmark } from '@/api/hooks/useQuant';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

// --- Empty fallback -----------------------------------------------------
// No hardcoded sample indices. Live data from GET /v1/benchmarks
// (src/api/routers/benchmarks.py) populates the table below.

const kpiData = [
  { label: 'Custom Indices', value: '—' },
  { label: 'Total Constituents', value: '—' },
  { label: 'Avg Return YTD', value: '—' },
  { label: 'Best Performing', value: '—' },
];

const weightingOptions = ['Equal'];

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-sm)',
  padding: '6px 10px',
  borderRadius: '4px',
  border: '1px solid var(--color-surface-border)',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-primary)',
  outline: 'none',
  width: '100%',
};

// --- Component ---------------------------------------------------------------

export default function CustomIndexBuilder() {
  const [name, setName] = useState('');
  const [tickersInput, setTickersInput] = useState('');
  // Equal weighting is the only method this form currently computes
  // client-side without fabricating market-cap/factor data it doesn't
  // have. The dropdown is kept (rather than removed) so the option is
  // visible/selectable for future wiring once that data is available.
  const [weighting] = useState('Equal');

  const { data: benchmarks } = useBenchmarks();
  const activeIndices = benchmarks ?? [];

  const [createError, setCreateError] = useState<string | null>(null);
  const createBenchmark = useCreateBenchmark();

  const handleCreateIndex = useCallback(async () => {
    setCreateError(null);
    const trimmedName = name.trim();
    if (!trimmedName) {
      setCreateError('Enter an index name.');
      return;
    }
    const tickers = Array.from(
      new Set(
        tickersInput
          .split(/[,\s]+/)
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean)
      )
    );
    if (tickers.length === 0) {
      setCreateError('Enter at least one constituent ticker (comma-separated).');
      return;
    }
    const weight = 1 / tickers.length;
    try {
      await createBenchmark.mutateAsync({
        name: trimmedName,
        constituents: tickers.map((ticker) => ({ ticker, weight })),
      });
      setName('');
      setTickersInput('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create index. Please try again.';
      setCreateError(message);
      console.error('[CustomIndexBuilder] create index failed:', err);
    }
  }, [name, tickersInput, createBenchmark]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Custom Index Builder
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Build and manage custom indices and benchmarks</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {kpiData.map((kpi) => (
          <div key={kpi.label} style={panelStyle}>
            <div style={labelStyle}>{kpi.label}</div>
            <div style={{ ...dataStyle, fontSize: 'var(--text-lg)', fontWeight: 600, marginTop: '4px' }}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* Index Configuration Form */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Index Configuration</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '16px', alignItems: 'end' }}>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Index Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter index name"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Constituent Tickers</label>
            <input
              type="text"
              value={tickersInput}
              onChange={(e) => setTickersInput(e.target.value)}
              placeholder="e.g. AAPL, MSFT, GOOGL"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Weighting Scheme</label>
            <select value={weighting} disabled style={inputStyle}>
              {weightingOptions.map((w) => (
                <option key={w} value={w}>{w}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleCreateIndex}
            disabled={createBenchmark.isPending}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '8px 20px',
              borderRadius: '4px',
              border: 'none',
              cursor: createBenchmark.isPending ? 'wait' : 'pointer',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-text-inverse)',
              whiteSpace: 'nowrap',
              opacity: createBenchmark.isPending ? 0.7 : 1,
            }}
          >
            {createBenchmark.isPending ? 'Creating…' : 'Create Index'}
          </button>
        </div>
        <p style={{ ...labelStyle, marginTop: '8px', fontSize: 'var(--text-xs)' }}>
          Equal-weighted only for now: each ticker gets a 1/N weight. Market-cap/factor
          weighting needs additional data this form doesn't collect yet.
        </p>
        {createError && (
          <div style={{ marginTop: '8px', padding: '6px 10px', borderRadius: '4px', background: 'color-mix(in srgb, var(--color-signal-negative) 10%, transparent)', color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)' }}>
            {createError}
          </div>
        )}
      </div>

      {/* Existing Benchmarks / Custom Indices Table */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>Benchmarks &amp; Custom Indices</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Name', 'Type', 'Ticker', 'Constituents', 'Created'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Constituents' ? 'right' : 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeIndices.map((b) => (
              <tr key={b.benchmark_id} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, color: 'var(--color-accent-primary)' }}>{b.name}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.benchmark_type}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{b.ticker ?? '—'}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.constituent_count ?? '—'}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>
                  {b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
