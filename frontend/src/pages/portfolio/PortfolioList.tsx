// ---------------------------------------------------------------------------
// Portfolio List — Portfolio Management Overview
// ---------------------------------------------------------------------------
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';

// --- Helpers -----------------------------------------------------------------

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatCurrency(value: number): string {
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

// --- Mock Data (fallback) ----------------------------------------------------

interface PortfolioRow {
  id: string;
  name: string;
  nav: number;
  dayChange: number;
  mtdReturn: number;
  ytdReturn: number;
  positions: number;
  status: 'Active' | 'Paper' | 'Archived';
}

const MOCK_PORTFOLIOS: PortfolioRow[] = [
  { id: 'p1', name: 'Core Growth',         nav: 2_458_320, dayChange: 0.34,  mtdReturn: 1.82,  ytdReturn: 8.42,  positions: 24, status: 'Active' },
  { id: 'p2', name: 'Value Opportunities', nav: 1_234_780, dayChange: -0.18, mtdReturn: -0.72, ytdReturn: 3.15,  positions: 18, status: 'Active' },
  { id: 'p3', name: 'Tech Alpha',          nav: 876_540,   dayChange: 0.92,  mtdReturn: 3.41,  ytdReturn: 14.28, positions: 12, status: 'Active' },
  { id: 'p4', name: 'Dividend Income',     nav: 3_125_600, dayChange: 0.08,  mtdReturn: 0.62,  ytdReturn: 4.87,  positions: 32, status: 'Active' },
  { id: 'p5', name: 'Small Cap Ideas',     nav: 425_180,   dayChange: -0.45, mtdReturn: -1.24, ytdReturn: -2.38, positions: 15, status: 'Paper' },
  { id: 'p6', name: 'ESG Focus',           nav: 685_200,   dayChange: 0.22,  mtdReturn: 0.95,  ytdReturn: 6.12,  positions: 20, status: 'Active' },
  { id: 'p7', name: 'Macro Hedge',         nav: 1_892_400, dayChange: -0.62, mtdReturn: 0.14,  ytdReturn: 1.88,  positions: 8,  status: 'Active' },
];

function statusBadgeClass(status: PortfolioRow['status']): string {
  switch (status) {
    case 'Active':   return 'terminal-badge terminal-badge-positive';
    case 'Paper':    return 'terminal-badge terminal-badge-neutral';
    case 'Archived': return 'terminal-badge';
  }
}

// --- Component ---------------------------------------------------------------

export default function PortfolioList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch portfolios
  const { data: portfolioData, isLoading } = useQuery<PortfolioRow[]>({
    queryKey: ['portfolios'],
    queryFn: () => api.get('/v4/portfolios'),
    retry: 0,
  });
  const portfolios = portfolioData ?? MOCK_PORTFOLIOS;

  // Create portfolio mutation
  const createMutation = useMutation({
    mutationFn: (name: string) => api.post('/v4/portfolios', { name }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
    onError: () => {
      // TODO: show toast notification
      console.warn('[PortfolioList] Create portfolio failed — API unavailable');
    },
  });

  const handleCreate = () => {
    createMutation.mutate('New Portfolio');
  };

  const handleRowClick = (id: string) => {
    navigate(`/portfolio/${id}`);
  };

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
            Portfolios
          </h1>
          <p className="terminal-label" style={{ marginTop: '4px' }}>
            {portfolios.length} portfolios &mdash; Total NAV {formatCurrency(portfolios.reduce((s, p) => s + p.nav, 0))}
          </p>
        </div>
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
                <th className="right">NAV</th>
                <th className="right">Day Chg</th>
                <th className="right">MTD</th>
                <th className="right">YTD</th>
                <th className="right">Positions</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {portfolios.map((p) => (
                <tr
                  key={p.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleRowClick(p.id)}
                >
                  <td style={{ fontWeight: 500, color: 'var(--color-accent-primary)' }}>
                    {p.name}
                  </td>
                  <td className="right">
                    {formatCurrency(p.nav)}
                  </td>
                  <td className="right" style={{ color: signalColor(p.dayChange) }}>
                    {formatPct(p.dayChange)}
                  </td>
                  <td className="right" style={{ color: signalColor(p.mtdReturn) }}>
                    {formatPct(p.mtdReturn)}
                  </td>
                  <td className="right" style={{ color: signalColor(p.ytdReturn) }}>
                    {formatPct(p.ytdReturn)}
                  </td>
                  <td className="right">
                    {p.positions}
                  </td>
                  <td>
                    <span className={statusBadgeClass(p.status)}>{p.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
