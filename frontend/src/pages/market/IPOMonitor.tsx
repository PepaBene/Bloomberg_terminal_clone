// ---------------------------------------------------------------------------
// IPO Monitor — Pipeline + Trading IPOs (real backend data)
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { EmptyState } from '@/components/feedback';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

// --- DTO (snake_case, mirrors src/schemas/ipo.py: IPOEventResponse) ----------

interface IPOEventDTO {
  ipo_id: string;
  s1_filing_date: string | null;
  pricing_date: string | null;
  trading_start_date: string | null;
  initial_range_low: number | null;
  initial_range_high: number | null;
  offer_price: number | null;
  total_proceeds: number | null;
  current_price: number | null;
  return_vs_offer_pct: number | null;
  lead_underwriters: string[] | null;
  company_description: string | null;
  gics_sector: string | null;
  status: string | null;
}

interface IPOResponse {
  data: IPOEventDTO[];
}

// --- Formatting helpers ------------------------------------------------------

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function fmtPrice(v: number | null | undefined): string {
  return v == null ? '—' : `$${v.toFixed(2)}`;
}

function fmtRange(low: number | null, high: number | null): string {
  if (low == null && high == null) return '—';
  return `$${(low ?? 0).toFixed(2)} – $${(high ?? 0).toFixed(2)}`;
}

const returnColor = (val: number | null | undefined): string =>
  val == null ? 'var(--color-text-primary)' : val >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';

// --- Component ---------------------------------------------------------------

export default function IPOMonitor() {
  // "Upcoming" ≈ pipeline (FILED / AMENDED) via the dedicated pipeline endpoint.
  const { data: pipelineResp, isLoading: pipelineLoading } = useQuery({
    queryKey: ['ipos', 'pipeline'],
    queryFn: () => api.get<IPOResponse>('/v1/ipos/pipeline', { page_size: 100 }),
    retry: 0,
  });
  // "Recent" ≈ IPOs already trading (have offer/current price + return).
  const { data: tradingResp, isLoading: tradingLoading } = useQuery({
    queryKey: ['ipos', 'trading'],
    queryFn: () => api.get<IPOResponse>('/v1/ipos', { status: 'TRADING', page_size: 100 }),
    retry: 0,
  });

  const upcoming = pipelineResp?.data ?? [];
  const recent = tradingResp?.data ?? [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          IPO Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Pipeline offerings and aftermarket performance</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {/* Upcoming / Pipeline IPOs — /v1/ipos/pipeline */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Upcoming IPOs (Pipeline)</h2>
          {pipelineLoading ? (
            <EmptyState title="Loading pipeline…" />
          ) : upcoming.length === 0 ? (
            <EmptyState icon="📋" title="No pipeline IPOs" description="No filed or amended IPOs were returned by the backend." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Filing Date', 'Company', 'Sector', 'Price Range', 'Proceeds', 'Lead Underwriter'].map((h) => (
                    <th
                      key={h}
                      style={{
                        ...labelStyle,
                        textAlign: h === 'Company' || h === 'Sector' || h === 'Lead Underwriter' ? 'left' : 'right',
                        padding: 'var(--table-cell-py) var(--table-cell-px)',
                        borderBottom: '1px solid var(--color-surface-border)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {upcoming.map((ipo) => (
                  <tr key={ipo.ipo_id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ipo.s1_filing_date ?? '—'}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{ipo.company_description ?? '—'}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.gics_sector ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtRange(ipo.initial_range_low, ipo.initial_range_high)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtMoney(ipo.total_proceeds)}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.lead_underwriters?.join(', ') ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Recent / Trading IPOs — /v1/ipos?status=TRADING */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Recent IPOs (Trading)</h2>
          {tradingLoading ? (
            <EmptyState title="Loading recent IPOs…" />
          ) : recent.length === 0 ? (
            <EmptyState icon="📈" title="No trading IPOs" description="No IPOs with TRADING status were returned by the backend." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Trading Start', 'Company', 'Offer Price', 'Current Price', 'Return vs Offer'].map((h) => (
                    <th
                      key={h}
                      style={{
                        ...labelStyle,
                        textAlign: h === 'Company' ? 'left' : 'right',
                        padding: 'var(--table-cell-py) var(--table-cell-px)',
                        borderBottom: '1px solid var(--color-surface-border)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((ipo) => (
                  <tr key={ipo.ipo_id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ipo.trading_start_date ?? '—'}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{ipo.company_description ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPrice(ipo.offer_price)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtPrice(ipo.current_price)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: returnColor(ipo.return_vs_offer_pct), fontWeight: 600 }}>
                      {ipo.return_vs_offer_pct == null ? '—' : `${ipo.return_vs_offer_pct >= 0 ? '+' : ''}${ipo.return_vs_offer_pct.toFixed(2)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* IPO Performance Summary — no backend endpoint exists */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>IPO Performance Summary</h2>
          <EmptyState icon="📊" title="Performance summary not available" description="There is no aggregate IPO performance endpoint on the backend yet." />
        </div>
      </div>
    </div>
  );
}
