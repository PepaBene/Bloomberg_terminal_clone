// ---------------------------------------------------------------------------
// Custom Index Builder — Build & Manage Custom Indices / Benchmarks
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { BENCHMARKS } from '@/api/endpoints';

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

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const customIndices = [
  { id: 'idx-1', name: 'US Tech Leaders',       constituents: 42,  weighting: 'Market Cap', universe: 'S&P 500',      ytdReturn: 18.42, createdDate: '2026-01-15' },
  { id: 'idx-2', name: 'Global Value Tilt',      constituents: 128, weighting: 'Factor',     universe: 'Global',        ytdReturn: 7.86,  createdDate: '2025-11-02' },
  { id: 'idx-3', name: 'Equal Weight Mega Cap',  constituents: 50,  weighting: 'Equal',      universe: 'S&P 500',      ytdReturn: 12.14, createdDate: '2026-02-20' },
  { id: 'idx-4', name: 'Russell Quality Screen', constituents: 215, weighting: 'Factor',     universe: 'Russell 1000',  ytdReturn: 9.58,  createdDate: '2025-09-18' },
  { id: 'idx-5', name: 'Momentum Global 100',    constituents: 100, weighting: 'Market Cap', universe: 'Global',        ytdReturn: -2.34, createdDate: '2026-03-05' },
];

const kpiData = [
  { label: 'Custom Indices', value: '5' },
  { label: 'Total Constituents', value: '535' },
  { label: 'Avg Return YTD', value: '+9.13%', color: 'var(--color-signal-positive)' },
  { label: 'Best Performing', value: '+18.42%', color: 'var(--color-signal-positive)' },
];

const weightingOptions = ['Equal', 'Market Cap', 'Factor'];
const universeOptions = ['S&P 500', 'Russell 1000', 'Global'];

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
  const [weighting, setWeighting] = useState('Equal');
  const [universe, setUniverse] = useState('S&P 500');

  const { data: apiBenchmarks } = useQuery({
    queryKey: ['benchmarks', 'list'],
    queryFn: () => api.get(BENCHMARKS.list),
  });

  // [Bug 94 fix] — Try correct API response key first, then fallback
  const activeIndices = (apiBenchmarks as any)?.benchmarks ?? (apiBenchmarks as any)?.indices ?? customIndices;

  const handleCreateIndex = useCallback(async () => {
    if (!name.trim()) return;
    // [Bug 95 fix] — Don't POST to the list endpoint; use a proper create path
    try { await api.post(BENCHMARKS.list + '/create', { name, weighting, universe }); } catch {}
  }, [name, weighting, universe]);

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
            <div style={{ ...dataStyle, fontSize: 'var(--text-lg)', fontWeight: 600, marginTop: '4px', color: kpi.color ?? 'var(--color-text-primary)' }}>
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
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Weighting Scheme</label>
            <select
              value={weighting}
              onChange={(e) => setWeighting(e.target.value)}
              style={inputStyle}
            >
              {weightingOptions.map((w) => (
                <option key={w} value={w}>{w}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ ...labelStyle, display: 'block', marginBottom: '4px' }}>Universe</label>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              style={inputStyle}
            >
              {universeOptions.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleCreateIndex}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '8px 20px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-text-inverse)',
              whiteSpace: 'nowrap',
            }}
          >
            Create Index
          </button>
        </div>
      </div>

      {/* Existing Custom Indices Table */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>Existing Custom Indices</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Name', 'Constituents', 'Weight Scheme', 'YTD Return %', 'Created Date'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Name' || h === 'Weight Scheme' || h === 'Created Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeIndices.map((idx: any) => (
              <tr key={idx.id} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, color: 'var(--color-accent-primary)' }}>{idx.name}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{idx.constituents}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{idx.weighting}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(idx.ytdReturn), fontWeight: 600 }}>{idx.ytdReturn >= 0 ? '+' : ''}{idx.ytdReturn.toFixed(2)}%</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{idx.createdDate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
