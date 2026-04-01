// ---------------------------------------------------------------------------
// Report Export Modal — Phase 2.5
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { api } from '@/api/client';
import { EXPORTS } from '@/api/endpoints';

interface ReportExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  portfolioId?: string;
  entityId?: string;
}

type ExportFormat = 'pdf' | 'excel' | 'csv';

const REPORT_TYPES = [
  'Portfolio Summary',
  'Holdings Detail',
  'Performance Report',
  'Risk Report',
  'Company Profile',
] as const;

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0, 0, 0, 0.6)',
  zIndex: 1000,
};

const modalStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: '24px',
  width: '480px',
  maxHeight: '90vh',
  overflow: 'auto',
};

const sectionStyle: React.CSSProperties = {
  marginBottom: '16px',
};

const headingStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 16px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
  display: 'block',
  marginBottom: '6px',
};

const radioLabelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-primary)',
  marginRight: '16px',
  cursor: 'pointer',
};

const checkboxLabelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-primary)',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  marginBottom: '6px',
  cursor: 'pointer',
};

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-primary)',
  background: 'var(--color-surface-overlay)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '3px',
  padding: '6px 8px',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  width: '100%',
};

const buttonStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-base)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  background: 'var(--color-accent-primary)',
  border: 'none',
  borderRadius: '3px',
  padding: '8px 20px',
  cursor: 'pointer',
  width: '100%',
};

export function ReportExportModal(props: ReportExportModalProps) {
  const { isOpen, onClose, portfolioId, entityId } = props;

  const [format, setFormat] = useState<ExportFormat>('pdf');
  const [reportType, setReportType] = useState<string>(REPORT_TYPES[0]);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [charts, setCharts] = useState(true);
  const [benchmarks, setBenchmarks] = useState(true);
  const [commentary, setCommentary] = useState(false);

  const [pending, setPending] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    setPending(true);
    setDownloadUrl(null);
    setError(null);

    const endpoint =
      format === 'pdf' ? EXPORTS.exportPdf :
      format === 'excel' ? EXPORTS.exportExcel :
      EXPORTS.exportCsv;

    const payload = {
      portfolioId,
      entityId,
      reportType,
      dateRange: { start: startDate, end: endDate },
      options: { charts, benchmarks, commentary },
    };

    try {
      const res = await api.post<{ url?: string; downloadUrl?: string }>(endpoint, payload);
      setDownloadUrl(res.url ?? res.downloadUrl ?? '#');
    } catch (e: any) {
      setError(e?.detail ?? 'Export failed');
    } finally {
      setPending(false);
    }
  }, [format, reportType, startDate, endDate, charts, benchmarks, commentary, portfolioId, entityId]);

  if (!isOpen) return null;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <h2 style={headingStyle}>Export Report</h2>

        {/* Format selection */}
        <div style={sectionStyle}>
          <span style={labelStyle}>Format</span>
          <div>
            {(['pdf', 'excel', 'csv'] as ExportFormat[]).map((f) => (
              <label key={f} style={radioLabelStyle}>
                <input
                  type="radio"
                  name="exportFormat"
                  value={f}
                  checked={format === f}
                  onChange={() => setFormat(f)}
                />
                {' '}{f.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        {/* Report type */}
        <div style={sectionStyle}>
          <label style={labelStyle}>Report Type</label>
          <select
            style={selectStyle}
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
          >
            {REPORT_TYPES.map((rt) => (
              <option key={rt} value={rt}>{rt}</option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div style={sectionStyle}>
          <span style={labelStyle}>Date Range</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="date"
              style={{ ...inputStyle, flex: 1 }}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <input
              type="date"
              style={{ ...inputStyle, flex: 1 }}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>

        {/* Options */}
        <div style={sectionStyle}>
          <span style={labelStyle}>Options</span>
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={charts} onChange={(e) => setCharts(e.target.checked)} />
            Include charts
          </label>
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={benchmarks} onChange={(e) => setBenchmarks(e.target.checked)} />
            Include benchmarks
          </label>
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={commentary} onChange={(e) => setCommentary(e.target.checked)} />
            Include commentary
          </label>
        </div>

        {/* Generate button */}
        <button
          style={{ ...buttonStyle, opacity: pending ? 0.6 : 1 }}
          disabled={pending}
          onClick={handleGenerate}
        >
          {pending ? 'Generating...' : 'Generate Report'}
        </button>

        {/* Status area */}
        {pending && (
          <div style={{ marginTop: '12px', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
            Generating...
          </div>
        )}
        {downloadUrl && (
          <div style={{ marginTop: '12px', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>
            Report ready &mdash;{' '}
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--color-accent-primary)', textDecoration: 'underline' }}
            >
              Download
            </a>
          </div>
        )}
        {error && (
          <div style={{ marginTop: '12px', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-negative, #ef4444)' }}>
            {error}
          </div>
        )}

        {/* Close button */}
        <button
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
            background: 'transparent',
            border: '1px solid var(--color-surface-border)',
            borderRadius: '3px',
            padding: '6px 16px',
            cursor: 'pointer',
            marginTop: '12px',
            width: '100%',
          }}
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  );
}
