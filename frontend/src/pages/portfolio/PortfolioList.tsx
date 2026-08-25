// ---------------------------------------------------------------------------
// Portfolio List — Portfolio Management Overview
// ---------------------------------------------------------------------------
import { useState, useCallback } from 'react';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useToastStore } from '@/stores/toastStore';

// --- Helpers -----------------------------------------------------------------

function signalColor(value: number | undefined): string {
  return (value ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function formatCurrency(value: number | undefined): string {
  if (value === undefined) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

// --- Skeleton ----------------------------------------------------------------

function Skeleton({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-sm)',
      }}
    />
  );
}

// Real shape of GET /v4/portfolios (src/schemas/portfolio.py:PortfolioResponse) --
// there is no NAV/day-change/MTD/YTD on the wire anywhere for portfolios, only
// cash + type + status. Per-portfolio market value/P&L comes from a separate
// GET .../analytics call, fetched below one per row.
interface ApiPortfolio {
  id: string;
  portfolio_name: string;
  portfolio_type: string;
  base_currency: string;
  initial_cash: number;
  current_cash: number;
  status: string;
}

interface PortfolioAnalytics {
  total_positions: number;
  market_value: number;
  net_pnl: number;
}

function statusBadgeClass(status: string): string {
  switch (status.toUpperCase()) {
    case 'ACTIVE':   return 'terminal-badge terminal-badge-positive';
    case 'PAPER':    return 'terminal-badge terminal-badge-neutral';
    case 'ARCHIVED': return 'terminal-badge';
    default:         return 'terminal-badge terminal-badge-neutral';
  }
}

// --- Component ---------------------------------------------------------------

export default function PortfolioList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch portfolios
  const { data: portfolioData, isLoading } = useQuery<ApiPortfolio[]>({
    queryKey: ['portfolios'],
    queryFn: () => api.get('/v4/portfolios'),
    retry: 0,
  });
  const portfolios = portfolioData ?? [];

  // Per-portfolio market value / P&L / position count -- not present on the
  // list endpoint, computed at request time from live positions.
  const analyticsQueries = useQueries({
    queries: portfolios.map((p) => ({
      queryKey: ['portfolio-analytics', p.id],
      queryFn: () => api.get<PortfolioAnalytics>(`/v4/portfolios/${p.id}/analytics`),
      retry: 0,
      staleTime: 30_000,
    })),
  });
  const analyticsById = new Map(
    portfolios.map((p, i) => [p.id, analyticsQueries[i]?.data]),
  );

  // Create portfolio mutation
  // [Bug fix] PortfolioCreateRequest (src/schemas/portfolio.py) requires
  // portfolio_name/inception_date/initial_cash -- this previously posted
  // {name: "New Portfolio"}, which 422'd every time (wrong field entirely,
  // two other required fields missing). portfolio_name also has a real
  // uq_portfolio_user_name unique constraint, so a second click with the
  // same hardcoded name would have collided even once the fields were
  // right -- timestamp it instead.
  const createMutation = useMutation({
    mutationFn: (portfolioName: string) =>
      api.post('/v4/portfolios', {
        portfolio_name: portfolioName,
        inception_date: new Date().toISOString().slice(0, 10),
        initial_cash: 0,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
    onError: () => {
      useToastStore.getState().showToast('Failed to create portfolio — API unavailable.');
    },
  });

  const handleCreate = () => {
    createMutation.mutate(`New Portfolio ${new Date().toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}`);
  };

  const handleRowClick = (id: string) => {
    navigate(`/portfolio/${id}`);
  };

  // --- CSV Upload state -------------------------------------------------------
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<
    { ticker: string; shares: number; price: number }[] | null
  >(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = useCallback(
    async (file: File) => {
      setUploadFile(file);
      setUploadPreview(null);
      setIsUploading(true);
      try {
        const formData = new FormData();
        formData.append('file', file);
        const result = await api.post('/v4/portfolios/upload/preview', formData);
        setUploadPreview(
          (result as { positions: { ticker: string; shares: number; price: number }[] }).positions ??
            (result as { ticker: string; shares: number; price: number }[]),
        );
      } catch (err) {
        console.warn('[PortfolioList] CSV preview failed', err);
        useToastStore.getState().showToast('Failed to preview CSV — check the file format and try again.');
        setUploadPreview([]);
      } finally {
        setIsUploading(false);
      }
    },
    [],
  );

  const handleConfirmImport = useCallback(async () => {
    if (!uploadFile) return;
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      await api.post('/v4/portfolios/upload/commit', formData);
      void queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      setShowUpload(false);
      setUploadFile(null);
      setUploadPreview(null);
    } catch (err) {
      console.warn('[PortfolioList] CSV commit failed', err);
      useToastStore.getState().showToast('Failed to import positions from CSV. Please try again.');
    } finally {
      setIsUploading(false);
    }
  }, [uploadFile, queryClient]);

  const handleCancelUpload = useCallback(() => {
    setShowUpload(false);
    setUploadFile(null);
    setUploadPreview(null);
    setIsUploading(false);
  }, []);

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
            Portfolios
          </h1>
          <p className="terminal-label" style={{ marginTop: '4px' }}>
            {portfolios.length} portfolios &mdash; Total Cash{' '}
            {formatCurrency(portfolios.reduce((s, p) => s + (p.current_cash ?? 0), 0))}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => setShowUpload(true)}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 500,
              padding: '6px 16px',
              background: 'transparent',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-surface-border)',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Upload CSV
          </button>
          <button
            onClick={handleCreate}
            disabled={createMutation.isPending}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 500,
              padding: '6px 16px',
              background: 'var(--color-accent-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: createMutation.isPending ? 'wait' : 'pointer',
              opacity: createMutation.isPending ? 0.7 : 1,
            }}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Portfolio'}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="terminal-panel">
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} height="28px" />)}
          </div>
        ) : (
          <table className="terminal-table">
            <thead>
              <tr>
                <th>Name</th>
                <th className="right">Market Value</th>
                <th className="right">Cash</th>
                <th className="right">Net P&amp;L</th>
                <th className="right">Positions</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {portfolios.length === 0 ? (
                <tr><td colSpan={7} className="terminal-label" style={{ textAlign: 'center', padding: '20px' }}>No portfolios available.</td></tr>
              ) : portfolios.map((p) => {
                const analytics = analyticsById.get(p.id);
                return (
                  <tr
                    key={p.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleRowClick(p.id)}
                  >
                    <td style={{ fontWeight: 500, color: 'var(--color-accent-primary)' }}>
                      {p.portfolio_name}
                    </td>
                    <td className="right">
                      {formatCurrency(analytics?.market_value)}
                    </td>
                    <td className="right">
                      {formatCurrency(p.current_cash)}
                    </td>
                    <td className="right" style={{ color: signalColor(analytics?.net_pnl) }}>
                      {analytics ? formatCurrency(analytics.net_pnl) : '—'}
                    </td>
                    <td className="right">
                      {analytics?.total_positions ?? '—'}
                    </td>
                    <td>
                      {p.portfolio_type}
                    </td>
                    <td>
                      <span className={statusBadgeClass(p.status)}>{p.status}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* CSV Upload Modal */}
      {showUpload && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={handleCancelUpload}
        >
          <div
            className="animate-in"
            style={{
              background: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-5, 20px)',
              width: '560px',
              maxWidth: '95vw',
              maxHeight: '80vh',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-4, 16px)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-base)',
                  fontWeight: 600,
                  color: 'var(--color-text-primary)',
                }}
              >
                Import Positions from CSV
              </span>
              <button
                type="button"
                onClick={handleCancelUpload}
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

            {/* File input */}
            <div
              style={{
                border: '2px dashed var(--color-surface-border)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-5, 20px)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 'var(--space-2, 8px)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {uploadFile ? uploadFile.name : 'Select a CSV or Excel file to import'}
              </span>
              <input
                type="file"
                accept=".csv,.xlsx"
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleFileSelect(file);
                }}
              />
            </div>

            {/* Loading indicator */}
            {isUploading && !uploadPreview && (
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                Parsing file...
              </span>
            )}

            {/* Preview table */}
            {uploadPreview && uploadPreview.length > 0 && (
              <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
                <span
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-tertiary)',
                    display: 'block',
                    marginBottom: 'var(--space-2, 8px)',
                  }}
                >
                  Preview — {uploadPreview.length} position{uploadPreview.length !== 1 ? 's' : ''} found
                </span>
                <table className="terminal-table" style={{ fontSize: 'var(--text-sm)' }}>
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th className="right">Shares</th>
                      <th className="right">Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {uploadPreview.slice(0, 20).map((row, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 500, color: 'var(--color-accent-primary)' }}>
                          {row.ticker}
                        </td>
                        <td className="right">{row.shares}</td>
                        <td className="right">${Number(row.price).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {uploadPreview.length > 20 && (
                  <span
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-text-tertiary)',
                      marginTop: 'var(--space-1, 4px)',
                      display: 'block',
                    }}
                  >
                    +{uploadPreview.length - 20} more positions
                  </span>
                )}
              </div>
            )}

            {uploadPreview && uploadPreview.length === 0 && (
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--color-signal-negative)',
                }}
              >
                No positions found in file. Check the format and try again.
              </span>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 'var(--space-2, 8px)', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={handleCancelUpload}
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
                onClick={() => void handleConfirmImport()}
                disabled={!uploadPreview || uploadPreview.length === 0 || isUploading}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  padding: '6px 16px',
                  background: 'var(--color-accent-primary)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor:
                    !uploadPreview || uploadPreview.length === 0 || isUploading
                      ? 'not-allowed'
                      : 'pointer',
                  opacity:
                    !uploadPreview || uploadPreview.length === 0 || isUploading ? 0.5 : 1,
                }}
              >
                {isUploading ? 'Importing...' : 'Confirm Import'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
