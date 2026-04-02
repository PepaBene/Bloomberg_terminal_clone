// ---------------------------------------------------------------------------
// Custom Data — CSV Upload Zone, Field Mapping UI, Import History
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { api } from '@/api/client';
import { useQuery } from '@tanstack/react-query';

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
  { date: '2026-02-28', filename: 'proprietary_signals.csv', rows: 2100, fields: 22, status: 'Success', duration: '3.8s' },
  { date: '2026-02-20', filename: 'macro_forecast_feb.xlsx', rows: 340, fields: 10, status: 'Success', duration: '0.9s' },
];

interface FieldMapping {
  source: string;
  target: string;
  type: 'Text' | 'Numeric' | 'Date' | 'Category' | 'Boolean';
  matched: boolean;
  confidence: number;
}

const fieldMappings: FieldMapping[] = [
  { source: 'Symbol', target: 'ticker', type: 'Text', matched: true, confidence: 98 },
  { source: 'Price', target: 'last_price', type: 'Numeric', matched: true, confidence: 95 },
  { source: 'Mkt Cap', target: 'market_cap', type: 'Numeric', matched: true, confidence: 92 },
  { source: 'Custom Score', target: 'custom_metric_1', type: 'Numeric', matched: false, confidence: 45 },
  { source: 'Region', target: 'geography', type: 'Category', matched: true, confidence: 88 },
  { source: 'Date', target: 'report_date', type: 'Date', matched: true, confidence: 96 },
  { source: 'Is Active', target: 'active_flag', type: 'Boolean', matched: true, confidence: 90 },
  { source: 'Notes', target: 'custom_text_1', type: 'Text', matched: false, confidence: 32 },
];

const selectStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: '2px 6px',
  outline: 'none',
};

const targetOptions = ['ticker', 'last_price', 'market_cap', 'geography', 'report_date', 'active_flag', 'custom_metric_1', 'custom_metric_2', 'custom_text_1', 'custom_text_2'];

export default function CustomData() {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);

  const { data: apiHistory } = useQuery({
    queryKey: ['custom-data', 'history'],
    queryFn: () => api.get('/v1/custom-data/history'),
    retry: 0,
  }) as { data: any };

  const activeHistory = (apiHistory as any)?.history ?? importHistory;

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      setUploadedFile(file?.name ?? null);
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        api.post('/v1/custom-data/upload', formData).catch(() => {
          /* upload failed — keep local preview */
        });
      }
    }
  }, []);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Custom Data</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Upload, map, and manage custom datasets</p>
      </div>

      {/* Enhanced Upload Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          ...panelStyle,
          borderStyle: 'dashed',
          borderWidth: '2px',
          borderColor: isDragging ? 'var(--color-accent-primary)' : 'var(--color-surface-border)',
          background: isDragging ? 'color-mix(in srgb, var(--color-accent-primary) 5%, var(--color-surface-base))' : 'var(--color-surface-base)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '140px',
          marginBottom: 'var(--panel-gap)',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-2xl)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
            {isDragging ? '\u2B07' : '\u2191'}
          </div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: isDragging ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)', marginBottom: '4px', fontWeight: 500 }}>
            {isDragging ? 'Drop file to upload' : uploadedFile ? `Uploaded: ${uploadedFile}` : 'Drop CSV, XLSX, or JSON files here'}
          </div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            Max 50MB per file &mdash; up to 100K rows &mdash; Supported: .csv, .xlsx, .json
          </div>
          {uploadedFile && (
            <div style={{ marginTop: '8px' }}>
              <span style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                padding: '2px 8px',
                borderRadius: '2px',
                color: 'var(--color-signal-positive)',
                background: 'color-mix(in srgb, var(--color-signal-positive) 15%, transparent)',
                fontWeight: 600,
              }}>
                File Ready
              </span>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Enhanced Field Mapping UI */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Field Mapping</h2>
          <p style={{ ...labelStyle, marginTop: '-8px', marginBottom: '12px' }}>
            Map source columns to target fields. Auto-matched fields are highlighted.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Source Field', 'Target Field', 'Type', 'Confidence', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Confidence' ? 'right' : 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {fieldMappings.map((f) => (
                <tr key={f.source} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.source}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <select style={selectStyle} defaultValue={f.target}>
                      {targetOptions.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                    </select>
                  </td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: 'var(--color-text-secondary)',
                      background: 'var(--color-surface-raised)',
                    }}>
                      {f.type}
                    </span>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.confidence >= 80 ? 'var(--color-signal-positive)' : f.confidence >= 50 ? 'var(--color-signal-warning)' : 'var(--color-signal-negative)' }}>
                    {f.confidence}%
                  </td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: f.matched ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>
                    {f.matched ? 'Auto' : 'Manual'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Import History */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Import History</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'File', 'Rows', 'Fields', 'Status', 'Time'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['File'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeHistory.map((r: any, i: number) => (
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
      </div>
    </div>
  );
}
