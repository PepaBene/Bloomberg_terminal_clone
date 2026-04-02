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

// --- Mock Data ---------------------------------------------------------------

const kpiStats = [
  { label: 'Upcoming IPOs', value: '14' },
  { label: 'Priced This Week', value: '5' },
  { label: 'Avg First Day Return', value: '+18.3%' },
  { label: 'Total Raised YTD', value: '$42.7B' },
  { label: 'Pipeline Value', value: '$11.2B' },
  { label: 'Withdrawn', value: '3' },
];

const upcomingIpos = [
  { expectedDate: '2026-04-07', company: 'Klarna Group',       ticker: 'KLAR',  sector: 'Fintech',       priceRange: '$58 – $62',  dealSize: '$2.5B', leadUnderwriter: 'Goldman Sachs' },
  { expectedDate: '2026-04-09', company: 'Databricks Inc',     ticker: 'DBX',   sector: 'Enterprise SW', priceRange: '$72 – $78',  dealSize: '$4.0B', leadUnderwriter: 'Morgan Stanley' },
  { expectedDate: '2026-04-14', company: 'Stripe Inc',         ticker: 'STRP',  sector: 'Payments',      priceRange: '$45 – $50',  dealSize: '$8.0B', leadUnderwriter: 'JPMorgan' },
  { expectedDate: '2026-04-16', company: 'Medline Industries', ticker: 'MDLN',  sector: 'Healthcare',    priceRange: '$30 – $34',  dealSize: '$3.2B', leadUnderwriter: 'BofA Securities' },
  { expectedDate: '2026-04-21', company: 'Cerebras Systems',   ticker: 'CRBS',  sector: 'Semiconductors', priceRange: '$40 – $46', dealSize: '$1.8B', leadUnderwriter: 'Citigroup' },
  { expectedDate: '2026-04-28', company: 'Plaid Inc',          ticker: 'PLAD',  sector: 'Fintech',       priceRange: '$22 – $26',  dealSize: '$1.2B', leadUnderwriter: 'Goldman Sachs' },
];

const recentIpos = [
  { ipoDate: '2026-03-28', company: 'CoreWeave Inc',       ipoPrice: 40.00, currentPrice: 52.30, returnPct: 30.75, marketCap: '$22.4B' },
  { ipoDate: '2026-03-25', company: 'Ventyx Biosciences',  ipoPrice: 18.00, currentPrice: 21.60, returnPct: 20.00, marketCap: '$2.1B' },
  { ipoDate: '2026-03-21', company: 'Lineage Inc',         ipoPrice: 78.00, currentPrice: 83.46, returnPct: 7.00,  marketCap: '$18.7B' },
  { ipoDate: '2026-03-18', company: 'ServiceTitan',        ipoPrice: 71.00, currentPrice: 68.16, returnPct: -4.00, marketCap: '$9.8B' },
  { ipoDate: '2026-03-14', company: 'Sailpoint Technology',ipoPrice: 25.50, currentPrice: 29.33, returnPct: 15.00, marketCap: '$4.5B' },
  { ipoDate: '2026-03-10', company: 'Ibotta Inc',          ipoPrice: 88.00, currentPrice: 79.20, returnPct: -10.00,marketCap: '$3.6B' },
  { ipoDate: '2026-03-05', company: 'Reddit Inc',          ipoPrice: 34.00, currentPrice: 44.88, returnPct: 32.00, marketCap: '$12.1B' },
  { ipoDate: '2026-03-01', company: 'Astera Labs',         ipoPrice: 36.00, currentPrice: 43.92, returnPct: 22.00, marketCap: '$7.3B' },
];

const performanceSummary = [
  { period: '1 Week',  avgReturn: '+12.4%', medianReturn: '+8.2%',  positiveRate: '80%' },
  { period: '1 Month', avgReturn: '+18.3%', medianReturn: '+14.1%', positiveRate: '72%' },
  { period: '3 Month', avgReturn: '+9.7%',  medianReturn: '+5.6%',  positiveRate: '64%' },
  { period: 'YTD',     avgReturn: '+15.1%', medianReturn: '+10.8%', positiveRate: '68%' },
];

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
