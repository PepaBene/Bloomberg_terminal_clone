// ---------------------------------------------------------------------------
// Estimates — Consensus Analyst Estimates
//
// GET /v1/securities/{security_id}/consensus-estimates (src/api/routers/
// estimates.py) has real ConsensusEstimate data ingested by
// scripts.ingest_consensus_estimates, but nothing in the frontend ever
// called it -- the NavRail's Research flyout "Estimates" sub-item fell back
// to the parent /research page. Wired here as its own route.
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

interface ConsensusEstimateDTO {
  metric: string;
  period_end_date: string;
  fiscal_year: number;
  fiscal_quarter: number | null;
  period_type: string | null;
  mean: number | null;
  median: number | null;
  high: number | null;
  low: number | null;
  num_estimates: number | null;
  num_revisions_up: number | null;
  num_revisions_down: number | null;
}
interface PaginatedResponse<T> { data: T[] }

function fmtNum(v: number | null): string {
  return v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

export default function EstimatesPage() {
  const primary = useSecurityStore((s) => s.primary);
  const securityId = primary?.security_id;

  const { data, isLoading } = useQuery<PaginatedResponse<ConsensusEstimateDTO>>({
    queryKey: ['research', 'estimates', securityId],
    queryFn: () => api.get(`/v1/securities/${securityId}/consensus-estimates`, { page_size: 50 }),
    enabled: !!securityId,
    retry: 0,
  });
  const estimates = data?.data ?? [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Consensus Estimates
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {primary?.ticker ?? '—'} {primary?.name ? `— ${primary.name}` : ''}
        </p>
      </div>

      <div style={panelStyle}>
        {!securityId ? (
          <EmptyState icon="📈" title="No security selected" description="Search for a company to view analyst consensus estimates." />
        ) : isLoading ? (
          <EmptyState icon="⏳" title="Loading…" />
        ) : estimates.length === 0 ? (
          <EmptyState icon="📈" title="No consensus estimates available" description="No analyst estimates have been ingested for this security yet." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Metric', 'Period', 'Mean', 'Median', 'Low', 'High', '# Estimates', 'Revisions ↑/↓'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {estimates.map((e, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{e.metric}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>
                    FY{e.fiscal_year}{e.fiscal_quarter ? ` Q${e.fiscal_quarter}` : ''} ({e.period_end_date})
                  </td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{fmtNum(e.mean)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtNum(e.median)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtNum(e.low)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtNum(e.high)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.num_estimates ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{ color: 'var(--color-signal-positive)' }}>{e.num_revisions_up ?? 0}↑</span>{' '}
                    <span style={{ color: 'var(--color-signal-negative)' }}>{e.num_revisions_down ?? 0}↓</span>
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
