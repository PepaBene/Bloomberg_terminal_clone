// ---------------------------------------------------------------------------
// IPO Monitor — Upcoming IPOs, Recent Pricings, Performance Tracker
// ---------------------------------------------------------------------------
import { useIpoUpcoming, useIpoRecent, useIpoPerformance, useIpoCalendar } from '@/hooks';

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

// --- Default empty data (populated by API) -----------------------------------

const kpiStats = [
  { label: 'Upcoming IPOs', value: '—' },
  { label: 'Priced This Week', value: '—' },
  { label: 'Avg First Day Return', value: '—' },
  { label: 'Total Raised YTD', value: '—' },
  { label: 'Pipeline Value', value: '—' },
  { label: 'Withdrawn', value: '—' },
];

const upcomingIpos: any[] = [];

const recentIpos: any[] = [];

const performanceSummary: any[] = [];

// --- Component ---------------------------------------------------------------

export default function IPOMonitor() {
  const { data: apiUpcoming } = useIpoUpcoming() as { data: any };
  const { data: apiRecent } = useIpoRecent() as { data: any };
  const { data: apiPerformance } = useIpoPerformance() as { data: any };
  const { data: apiCalendar } = useIpoCalendar() as { data: any };

  const activeKpis = (apiCalendar as any)?.stats ?? kpiStats;
  const activeUpcoming = (apiUpcoming as any)?.ipos ?? upcomingIpos;
  const activeRecent = (apiRecent as any)?.ipos ?? recentIpos;
  const activePerformance = (apiPerformance as any)?.summary ?? performanceSummary;

  const returnColor = (val: number) =>
    val >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          IPO Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Upcoming offerings, recent pricings, and aftermarket performance</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeKpis.map((s: any) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {/* Upcoming IPOs */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Upcoming IPOs</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Expected Date', 'Company', 'Ticker', 'Sector', 'Price Range', 'Deal Size', 'Lead Underwriter'].map((h) => (
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
              {activeUpcoming.map((ipo: any) => (
                <tr key={ipo.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ipo.expectedDate}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{ipo.company}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{ipo.ticker}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.sector}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.priceRange}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.dealSize}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.leadUnderwriter}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent IPOs */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Recent IPOs</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['IPO Date', 'Company', 'IPO Price', 'Current Price', 'Return %', 'Market Cap'].map((h) => (
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
              {activeRecent.map((ipo: any) => (
                <tr key={ipo.company} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{ipo.ipoDate}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{ipo.company}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${ipo.ipoPrice.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${ipo.currentPrice.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: returnColor(ipo.returnPct), fontWeight: 600 }}>
                    {ipo.returnPct >= 0 ? '+' : ''}{ipo.returnPct.toFixed(2)}%
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ipo.marketCap}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* IPO Performance */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>IPO Performance Summary</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Period', 'Avg Return', 'Median Return', 'Positive Rate'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: h === 'Period' ? 'left' : 'right',
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
              {activePerformance.map((row: any) => (
                <tr key={row.period} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{row.period}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>{row.avgReturn}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>{row.medianReturn}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{row.positiveRate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
