// ---------------------------------------------------------------------------
// Custom Data — CSV Upload Zone, Field Mapping, Import History
//
// NOTE: There is no CSV-import backend. custom_data.py only exposes
// /v1/analytics/custom-fields* (expression-based computed fields — a
// different feature). There is no upload endpoint and no import-history
// endpoint. The upload zone below therefore previews the picked file name
// locally only; it does not persist anything server-side. Field Mapping and
// Import History have no real data source and render honest empty states.
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { EmptyState, DemoModeBanner } from '@/components/feedback';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

export default function CustomData() {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);

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
      // Local preview only — there is no upload endpoint on the backend, so
      // we intentionally do NOT POST the file anywhere (that would fail
      // silently and mislead the user into thinking it saved).
      setUploadedFile(files[0]?.name ?? null);
    }
  }, []);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Custom Data</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Upload, map, and manage custom datasets</p>
      </div>

      <DemoModeBanner
        severity="info"
        message="CSV import is not yet backed by a server endpoint — uploads are previewed locally only."
      />

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
            {isDragging ? '⬇' : '↑'}
          </div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: isDragging ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)', marginBottom: '4px', fontWeight: 500 }}>
            {isDragging ? 'Drop file to preview' : uploadedFile ? `Selected: ${uploadedFile}` : 'Drop CSV, XLSX, or JSON files here'}
          </div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            Previewed locally &mdash; not uploaded &mdash; Supported: .csv, .xlsx, .json
          </div>
          {uploadedFile && (
            <div style={{ marginTop: '8px' }}>
              <span style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                padding: '2px 8px',
                borderRadius: '2px',
                color: 'var(--color-text-secondary)',
                background: 'var(--color-surface-raised)',
                fontWeight: 600,
              }}>
                Local Preview
              </span>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Field Mapping — no backend parses uploads, so there is nothing real to map. */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Field Mapping</h2>
          <EmptyState
            icon="🔗"
            title="No field mappings"
            description="Column-to-field mapping requires a server-side upload parser, which is not implemented. Nothing is inferred from local previews."
          />
        </div>

        {/* Import History — no import-history endpoint exists. */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Import History</h2>
          <EmptyState
            icon="🗂"
            title="No imports yet"
            description="There is no import backend, so no import history is recorded. Uploaded files are previewed locally only and are not persisted."
          />
        </div>
      </div>
    </div>
  );
}
