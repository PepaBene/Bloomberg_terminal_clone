import { useState, useRef, useCallback } from 'react';
import type { CSSProperties, DragEvent, ChangeEvent } from 'react';
import { api } from '@/api/client';
import { DataTable } from '@/components/ui/DataTable';
import type { Column } from '@/components/ui/DataTable';

export interface CSVUploadDialogProps {
  portfolioId: string;
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface PreviewRow {
  ticker: string;
  shares: string;
  price: string;
  date: string;
  direction: string;
  [key: string]: unknown;
}

function parseCSV(text: string): PreviewRow[] {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0]!.split(',').map((h) => h.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const cells = line.split(',').map((c) => c.trim());
    const row: Record<string, string> = {};
    headers.forEach((h, i) => { row[h] = cells[i] ?? ''; });
    return {
      ticker: row['ticker'] ?? '',
      shares: row['shares'] ?? '',
      price: row['price'] ?? '',
      date: row['date'] ?? '',
      direction: row['direction'] ?? '',
    } as PreviewRow;
  });
}

const previewColumns: Column<PreviewRow>[] = [
  { key: 'ticker', name: 'Ticker', width: '80px' },
  { key: 'direction', name: 'Dir', width: '60px' },
  { key: 'shares', name: 'Shares', width: '80px', align: 'right' },
  { key: 'price', name: 'Price', width: '80px', align: 'right' },
  { key: 'date', name: 'Date', width: '100px' },
];

export function CSVUploadDialog({
  portfolioId,
  open,
  onClose,
  onSuccess,
}: CSVUploadDialogProps) {
  const [dragging, setDragging] = useState(false);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback((file: File) => {
    setRawFile(file);
    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      setPreviewRows(rows);
    };
    reader.readAsText(file);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile],
  );

  const onFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) processFile(file);
    },
    [processFile],
  );

  const handleSubmit = async () => {
    if (!rawFile) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', rawFile);
      await api.post(`/v1/portfolios/${portfolioId}/upload`, formData);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  const overlayStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const dialogStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-5)',
    width: '580px',
    maxWidth: '95vw',
    maxHeight: '80vh',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-4)',
  };

  const dropZoneStyle: CSSProperties = {
    border: `2px dashed ${dragging ? 'var(--color-accent-primary)' : 'var(--color-surface-border)'}`,
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-6)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--space-2)',
    cursor: 'pointer',
    transition: 'border-color 0.15s',
    background: dragging ? 'var(--color-surface-raised)' : 'transparent',
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        className="animate-in"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-base)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
            }}
          >
            Import CSV
          </span>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-text-tertiary)',
              fontSize: 'var(--text-base)',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        <div
          style={dropZoneStyle}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <span style={{ fontSize: '24px' }}>&#x1F4C4;</span>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-secondary)',
            }}
          >
            {rawFile ? rawFile.name : 'Drop CSV here or click to browse'}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            Columns: ticker, shares, price, date, direction
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={onFileChange}
          />
        </div>

        {previewRows.length > 0 && (
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            <div
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-tertiary)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Preview — {previewRows.length} row{previewRows.length !== 1 ? 's' : ''} found
            </div>
            <DataTable<PreviewRow>
              columns={previewColumns}
              data={previewRows.slice(0, 10)}
              compact
            />
            {previewRows.length > 10 && (
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  marginTop: 'var(--space-1)',
                }}
              >
                +{previewRows.length - 10} more rows
              </div>
            )}
          </div>
        )}

        {error && (
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-signal-negative)',
            }}
          >
            {error}
          </span>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 16px',
              background: 'transparent',
              color: 'var(--color-text-tertiary)',
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!rawFile || loading}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '6px 16px',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-surface-void)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: !rawFile || loading ? 'not-allowed' : 'pointer',
              opacity: !rawFile || loading ? 0.5 : 1,
            }}
          >
            {loading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CSVUploadDialog;
