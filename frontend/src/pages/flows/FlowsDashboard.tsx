// ---------------------------------------------------------------------------
// Flows Dashboard — Institutional Flows, Sector Rotation, Whale Alerts
// ---------------------------------------------------------------------------
import { api } from '@/api/client';
import { EmptyState } from '@/components/feedback';
import { useQuery } from '@tanstack/react-query';

// Real backend routes. The flows router self-prefixes /v2/analytics
// (src/api/routers/flows.py). The FLOWS constants in endpoints.ts point at
// legacy /v1 paths that 404, so the correct paths are inlined here.
const MARKET_FLOW_PATH = '/v2/analytics/flows/market';
const SECTOR_FLOW_PATH = '/v2/analytics/flows/sectors';
const WHALE_MOVES_PATH = '/v2/analytics/flows/alerts/whale-moves';

// --- DTOs mirroring the backend Pydantic schemas (src/schemas/flows.py) ------

interface MarketFlowResponse {
  report_date: string | null;
  total_new_positions: number | null;
  total_closed_positions: number | null;
  net_institutional_flow: number | null;
  breadth_score: number | null;
}

interface SectorFlowResponse {
  gics_sector: string;
  sector_name: string | null;
  net_flow: number | null;
  new_positions: number | null;
  closed_positions: number | null;
}

interface FlowAlertResponse {
  alert_id: string;
  alert_type: string;
  security_id: string;
  ticker: string | null;
  institution_name: string | null;
  headline: string;
  report_date: string;
  shares_involved: number | null;
  value_involved: number | null;
  percent_of_outstanding: number | null;
  severity: string;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// --- Formatting helpers ------------------------------------------------------

function fmtCurrency(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  const sign = v < 0 ? '-' : '+';
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function fmtNumber(v: number | null | undefined): string {
  if (v == null) return '—';
  return v.toLocaleString();
}

export default function FlowsDashboard() {
  const { data: market } = useQuery<MarketFlowResponse>({
    queryKey: ['flows', 'market'],
    queryFn: () => api.get<MarketFlowResponse>(MARKET_FLOW_PATH),
    retry: 0,
  });
  const { data: sectors } = useQuery<SectorFlowResponse[]>({
    queryKey: ['flows', 'sectors'],
    queryFn: () => api.get<SectorFlowResponse[]>(SECTOR_FLOW_PATH),
    retry: 0,
  });
  const { data: whales } = useQuery<FlowAlertResponse[]>({
    queryKey: ['flows', 'whaleMoves'],
    queryFn: () => api.get<FlowAlertResponse[]>(WHALE_MOVES_PATH),
    retry: 0,
  });

  const netFlow = market?.net_institutional_flow ?? null;
  const kpis = [
    { label: 'Net Institutional Flow', value: fmtCurrency(netFlow), positive: netFlow != null && netFlow >= 0 },
    { label: 'New Positions', value: fmtNumber(market?.total_new_positions), positive: false },
    { label: 'Closed Positions', value: fmtNumber(market?.total_closed_positions), positive: false },
    { label: 'Breadth Score', value: market?.breadth_score != null ? market.breadth_score.toFixed(2) : '—', positive: false },
    { label: 'As Of', value: market?.report_date ?? '—', positive: false },
  ];
  const hasMarket = !!market && (
    market.net_institutional_flow != null ||
    market.total_new_positions != null ||
    market.total_closed_positions != null ||
    market.breadth_score != null
  );

  const whaleRows = whales ?? [];
  const sectorRows = sectors ?? [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Institutional Flows</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Market-wide institutional flow, sector rotation, and whale alerts (13F)</p>
      </div>

      {hasMarket ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
          {kpis.map((k) => (
            <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
              <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: k.positive ? 'var(--color-signal-positive)' : 'var(--color-text-primary)' }}>{k.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
          <EmptyState icon="📊" title="No market flow data" description="No institutional flow signals are available for the latest reporting period." />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Whale Moves</h2>
          {whaleRows.length === 0 ? (
            <EmptyState icon="🐋" title="No whale alerts" description="No large position changes by whale-tier institutions have been flagged." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                {['Date', 'Institution', 'Ticker', 'Shares', 'Est. Value'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: ['Institution'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {whaleRows.map((t) => (
                  <tr key={t.alert_id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{t.report_date}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{t.institution_name ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{t.ticker ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtNumber(t.shares_involved)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{fmtCurrency(t.value_involved)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div style={panelStyle}>
          <h2 style={sectionTitle}>Sector Rotation</h2>
          {sectorRows.length === 0 ? (
            <EmptyState icon="📈" title="No sector flow data" description="No sector-level institutional flow is available for the latest reporting period." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                {['Sector', 'Net Flow', 'New', 'Closed'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Sector' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {sectorRows.map((s) => (
                  <tr key={s.gics_sector} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sector_name ?? s.gics_sector}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: (s.net_flow ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{fmtCurrency(s.net_flow)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)' }}>{fmtNumber(s.new_positions)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{fmtNumber(s.closed_positions)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
