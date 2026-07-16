// ---------------------------------------------------------------------------
// Deals View — M&A Deals + Statistics (real backend data)
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { EmptyState } from '@/components/feedback';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// --- DTOs (snake_case, mirror src/schemas/ma_deals.py) -----------------------

interface MandADealDTO {
  deal_id: string;
  acquirer_name: string | null;
  target_name: string | null;
  deal_type: string | null;
  deal_status: string | null;
  total_value: number | null;
  premium_to_undisturbed: number | null;
  announcement_date: string | null;
}

interface DealsResponse {
  data: MandADealDTO[];
}

interface DealStatisticsResponse {
  total_deals: number;
  total_value: number | null;
  avg_premium: number | null;
  avg_ev_to_ebitda: number | null;
}

// --- Formatting helpers ------------------------------------------------------

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function fmtPct(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(1)}%`;
}

// deal_status values come from the DealStatus enum (PENDING/COMPLETED/TERMINATED/WITHDRAWN).
const statusColor = (s: string | null): string => {
  switch (s) {
    case 'COMPLETED': return 'var(--color-signal-positive)';
    case 'PENDING': return 'var(--color-signal-warning)';
    case 'TERMINATED':
    case 'WITHDRAWN': return 'var(--color-signal-negative)';
    default: return 'var(--color-text-secondary)';
  }
};

export default function DealsView() {
  const { data: dealsResp, isLoading: dealsLoading } = useQuery({
    queryKey: ['deals', 'list'],
    queryFn: () => api.get<DealsResponse>('/v1/deals', { page_size: 100 }),
    retry: 0,
  });
  const { data: stats } = useQuery({
    queryKey: ['deals', 'statistics'],
    queryFn: () => api.get<DealStatisticsResponse>('/v1/deals/statistics'),
    retry: 0,
  });

  const deals = dealsResp?.data ?? [];

  const kpis = [
    { label: 'Total Deals', value: stats ? stats.total_deals.toLocaleString() : '—' },
    { label: 'Total Deal Value', value: fmtMoney(stats?.total_value) },
    { label: 'Average Premium', value: fmtPct(stats?.avg_premium) },
    { label: 'Average EV/EBITDA', value: stats?.avg_ev_to_ebitda != null ? `${stats.avg_ev_to_ebitda.toFixed(1)}x` : '—' },
  ];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>M&A Deals</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Active transactions and market statistics</p>
      </div>
      {/* KPI Row — derived from /v1/deals/statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {kpis.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      {/* Active Deals Table — /v1/deals */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Active Deals</h2>
        {dealsLoading ? (
          <EmptyState title="Loading deals…" />
        ) : deals.length === 0 ? (
          <EmptyState icon="🤝" title="No deals available" description="No M&A deals were returned by the backend." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'Acquirer', 'Target', 'Deal Value', 'Premium %', 'Status', 'Type'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['Acquirer', 'Target', 'Status', 'Type'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {deals.map((d) => (
                <tr key={d.deal_id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.announcement_date ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.acquirer_name ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 500 }}>{d.target_name ?? '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{fmtMoney(d.total_value)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPct(d.premium_to_undisturbed)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: statusColor(d.deal_status), fontWeight: 500 }}>{d.deal_status ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>{d.deal_type ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {/* Deal Pipeline — no backend endpoint exists */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>Deal Pipeline</h2>
        <EmptyState icon="🗂️" title="Pipeline not available" description="There is no deal pipeline endpoint on the backend yet." />
      </div>
    </div>
  );
}
