// ---------------------------------------------------------------------------
// Company Peers — Competitive Peer Comparison
//
// GET /v3/competitive/{entity_id}/peers (src/api/routers/competitive.py) has
// existed with real data since the competitive-intelligence engine shipped,
// but nothing in the frontend ever called it -- the NavRail's Company flyout
// "Peers" sub-item fell back to the parent /company page. Wired here as its
// own real route.
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { useSecurityStore } from '@/stores/securityContext';
import { EmptyState } from '@/components/feedback';
import { api } from '@/api/client';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
};
const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
};

interface PeerComparisonDTO {
  entity_id: string;
  entity_name: string | null;
  market_share_est_pct: number | null;
  market_share_rank: number | null;
  revenue_growth_vs_peers: number | null;
  margin_vs_peers: number | null;
  roic_vs_peers: number | null;
}

function fmtPct(v: number | null): string {
  return v === null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

export default function CompanyPeers() {
  const primary = useSecurityStore((s) => s.primary);
  const entityId = primary?.entity_id;

  const { data, isLoading } = useQuery<PeerComparisonDTO[]>({
    queryKey: ['company', 'peers', entityId],
    queryFn: () => api.get(`/v3/competitive/${entityId}/peers`),
    enabled: !!entityId,
    retry: 0,
  });
  const peers = Array.isArray(data) ? data : [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Peer Comparison
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {primary?.ticker ?? '—'} {primary?.name ? `— ${primary.name}` : ''}
        </p>
      </div>

      <div style={panelStyle}>
        {!entityId ? (
          <EmptyState icon="🏢" title="No company selected" description="Search for a company to view its competitive peer comparison." />
        ) : isLoading ? (
          <EmptyState icon="⏳" title="Loading…" />
        ) : peers.length === 0 ? (
          <EmptyState icon="🏢" title="No peer comparison available" description="Competitive-intelligence peer data has not been computed for this company yet." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Peer', 'Mkt Share', 'Share Rank', 'Rev Growth vs Peers', 'Margin vs Peers', 'ROIC vs Peers'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {peers.map((p) => (
                <tr key={p.entity_id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{p.entity_name ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.market_share_est_pct != null ? `${p.market_share_est_pct.toFixed(1)}%` : '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.market_share_rank ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPct(p.revenue_growth_vs_peers)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPct(p.margin_vs_peers)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPct(p.roic_vs_peers)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
