// ---------------------------------------------------------------------------
// Custom Data — Upload, Field Mapping, Import History
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const importHistory = [
  { date: '2026-03-25', filename: 'portfolio_positions_q1.csv', rows: 1248, fields: 18, status: 'Success', duration: '2.3s' },
  { date: '2026-03-20', filename: 'custom_scores_v2.xlsx', rows: 520, fields: 12, status: 'Success', duration: '1.8s' },
  { date: '2026-03-15', filename: 'peer_comps_march.csv', rows: 85, fields: 24, status: 'Success', duration: '0.4s' },
  { date: '2026-03-10', filename: 'esg_ratings_internal.csv', rows: 3200, fields: 8, status: 'Partial (12 errors)', duration: '5.1s' },
  { date: '2026-03-05', filename: 'hedge_fund_holdings.xlsx', rows: 445, fields: 15, status: 'Success', duration: '1.2s' },
];

const fieldMappings = [
  { source: 'Symbol', target: 'ticker', type: 'Text', matched: true },
  { source: 'Price', target: 'last_price', type: 'Numeric', matched: true },
  { source: 'Mkt Cap', target: 'market_cap', type: 'Numeric', matched: true },
  { source: 'Custom Score', target: 'custom_metric_1', type: 'Numeric', matched: false },
  { source: 'Region', target: 'geography', type: 'Category', matched: true },
];

export default function CustomData() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Custom Data</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Upload, map, and manage custom datasets</p>
      </div>
      {/* Upload Zone */}
      <div style={{ ...panelStyle, borderStyle: 'dashed', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100px', marginBottom: 'var(--panel-gap)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Drop CSV, XLSX, or JSON files here</div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Max 50MB per file &mdash; up to 100K rows</div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Import History</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'File', 'Rows', 'Fields', 'Status', 'Time'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['File'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {importHistory.map((r, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.date}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.filename}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.rows.toLocaleString()}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.fields}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: r.status === 'Success' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)', fontSize: 'var(--text-sm)' }}>{r.status}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-tertiary)' }}>{r.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Field Mapping</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Source Field', 'Target Field', 'Type', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {fieldMappings.map((f) => (
                <tr key={f.source} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.source}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.target}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.type}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.matched ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{f.matched ? 'Matched' : 'Manual'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
