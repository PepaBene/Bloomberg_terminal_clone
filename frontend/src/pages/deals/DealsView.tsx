// ---------------------------------------------------------------------------
// Deals View — M&A Deals, Pipeline, Statistics
// ---------------------------------------------------------------------------
import { useDeals, useDealsPipeline, useDealsStatistics } from '@/hooks';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const dealKPIs = [
  { label: 'Total Deals', value: '142' },
  { label: 'Pipeline Value', value: '$1.84T' },
  { label: 'Completed This Year', value: '38' },
  { label: 'Average Premium', value: '32.4%' },
  { label: 'Largest Deal', value: '$68.7B' },
  { label: 'Pending Regulatory', value: '17' },
];

const deals = [
  { date: '2026-03-28', acquirer: 'Microsoft', target: 'Figma', dealValue: '$22.0B', premium: 42.5, status: 'Pending', type: 'Tech / SaaS' },
  { date: '2026-03-25', acquirer: 'Broadcom', target: 'VMware', dealValue: '$68.7B', premium: 48.2, status: 'Completed', type: 'Semiconductors' },
  { date: '2026-03-22', acquirer: 'Pfizer', target: 'Seagen', dealValue: '$43.0B', premium: 33.0, status: 'Completed', type: 'Pharma' },
  { date: '2026-03-18', acquirer: 'Exxon Mobil', target: 'Pioneer Natural', dealValue: '$59.5B', premium: 18.4, status: 'Completed', type: 'Energy' },
  { date: '2026-03-15', acquirer: 'Cisco', target: 'Splunk', dealValue: '$28.0B', premium: 31.2, status: 'Pending', type: 'Cybersecurity' },
  { date: '2026-03-12', acquirer: 'Capital One', target: 'Discover Financial', dealValue: '$35.3B', premium: 26.6, status: 'Pending', type: 'Financials' },
  { date: '2026-03-08', acquirer: 'Alphabet', target: 'Wiz', dealValue: '$23.0B', premium: 55.0, status: 'Rumored', type: 'Cybersecurity' },
  { date: '2026-03-05', acquirer: 'Nippon Steel', target: 'U.S. Steel', dealValue: '$14.9B', premium: 40.1, status: 'Pending', type: 'Industrials' },
  { date: '2026-02-28', acquirer: 'Novo Holdings', target: 'Catalent', dealValue: '$16.5B', premium: 22.8, status: 'Completed', type: 'Pharma' },
  { date: '2026-02-20', acquirer: 'ConocoPhillips', target: 'Marathon Oil', dealValue: '$22.5B', premium: 14.7, status: 'Completed', type: 'Energy' },
];

const pipeline = [
  { acquirer: 'Amazon', target: 'iRobot', dealValue: '$1.7B', status: 'Regulatory Review', type: 'Consumer Tech' },
  { acquirer: 'JetBlue', target: 'Spirit Airlines', dealValue: '$3.8B', status: 'Blocked', type: 'Airlines' },
  { acquirer: 'Chevron', target: 'Hess Corp', dealValue: '$53.0B', status: 'Regulatory Review', type: 'Energy' },
  { acquirer: 'Tapestry', target: 'Capri Holdings', dealValue: '$8.5B', status: 'Antitrust Review', type: 'Luxury Retail' },
  { acquirer: 'Synopsys', target: 'Ansys', dealValue: '$35.0B', status: 'Due Diligence', type: 'EDA Software' },
  { acquirer: 'Diamondback Energy', target: 'Endeavor Energy', dealValue: '$26.0B', status: 'Shareholder Vote', type: 'Energy' },
];

const statistics = [
  { label: 'Total Deal Volume (YTD)', value: '$892B' },
  { label: 'Average Deal Size', value: '$6.3B' },
  { label: 'Cross-Border Deals', value: '34%' },
  { label: 'Hostile Takeovers', value: '4' },
  { label: 'All-Cash Deals', value: '62%' },
  { label: 'Stock-for-Stock', value: '21%' },
  { label: 'Deals Withdrawn (YTD)', value: '8' },
  { label: 'Avg Days to Close', value: '127' },
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
