// ---------------------------------------------------------------------------
// Deals View — M&A Deals, Pipeline, Statistics
// ---------------------------------------------------------------------------
import { useDeals, useDealsPipeline, useDealsStatistics } from '@/hooks';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const dealKPIs = [
  { label: 'Total Deals', value: '—' },
  { label: 'Pipeline Value', value: '—' },
  { label: 'Completed This Year', value: '—' },
  { label: 'Average Premium', value: '—' },
  { label: 'Largest Deal', value: '—' },
  { label: 'Pending Regulatory', value: '—' },
];

const deals: any[] = [];

const pipeline: any[] = [];

const statistics = [
  { label: 'Total Deal Volume (YTD)', value: '—' },
  { label: 'Average Deal Size', value: '—' },
  { label: 'Cross-Border Deals', value: '—' },
  { label: 'Hostile Takeovers', value: '—' },
  { label: 'All-Cash Deals', value: '—' },
  { label: 'Stock-for-Stock', value: '—' },
  { label: 'Deals Withdrawn (YTD)', value: '—' },
  { label: 'Avg Days to Close', value: '—' },
];

const statusColor = (s: string) => {
  if (s === 'Completed') return 'var(--color-signal-positive)';
  if (s === 'Pending' || s === 'Regulatory Review' || s === 'Antitrust Review' || s === 'Shareholder Vote' || s === 'Due Diligence') return 'var(--color-signal-warning)';
  if (s === 'Rumored') return 'var(--color-accent-primary)';
  if (s === 'Blocked') return 'var(--color-signal-negative)';
  return 'var(--color-text-secondary)';
};

export default function DealsView() {
  const { data: apiDeals } = useDeals() as { data: any };
  const { data: apiPipeline } = useDealsPipeline() as { data: any };
  const { data: apiStats } = useDealsStatistics() as { data: any };

  const activeDeals = (apiDeals as any)?.deals ?? deals;
  const activePipeline = (apiPipeline as any)?.pipeline ?? pipeline;
  const activeStats = (apiStats as any)?.statistics ?? statistics;
  const activeKPIs = (apiDeals as any)?.kpis ?? dealKPIs;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>M&A Deals</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Active transactions, deal pipeline, and market statistics</p>
      </div>
      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeKPIs.map((k: any) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>
      {/* Active Deals Table */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Active Deals</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Date', 'Acquirer', 'Target', 'Deal Value', 'Premium %', 'Status', 'Type'].map((h) => (
              <th key={h} style={{ ...labelStyle, textAlign: ['Acquirer', 'Target', 'Status', 'Type'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {activeDeals.map((d: any, i: number) => (
              <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.date}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.acquirer}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 500 }}>{d.target}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{d.dealValue}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.premium.toFixed(1)}%</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: statusColor(d.status), fontWeight: 500 }}>{d.status}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>{d.type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Pipeline + Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Deal Pipeline</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Acquirer', 'Target', 'Deal Value', 'Status', 'Type'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['Acquirer', 'Target', 'Status', 'Type'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activePipeline.map((p: any, i: number) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{p.acquirer}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 500 }}>{p.target}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.dealValue}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, color: statusColor(p.status), background: 'var(--color-surface-raised)', border: `1px solid ${statusColor(p.status)}`, borderRadius: '3px', padding: '2px 6px' }}>{p.status}</span>
                  </td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>{p.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Deal Statistics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {activeStats.map((s: any) => (
                <tr key={s.label} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{s.label}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, borderBottom: '1px solid var(--color-surface-border)' }}>{s.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
