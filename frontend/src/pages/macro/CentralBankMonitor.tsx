// ---------------------------------------------------------------------------
// Central Bank Monitor — Fed, ECB, BOJ, BOE Decisions & Forward Guidance
// ---------------------------------------------------------------------------
import { FedRateHistory, MacroIndicatorTable } from '@/components/macro';
import type { FedRatePoint, MacroIndicator } from '@/components/macro';
import { useCentralBanks, useMacroDashboardData } from '@/hooks';

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

const centralBanks = [
  { bank: 'Federal Reserve', rate: '5.25-5.50%', lastAction: 'Hold', lastDate: '2026-03-19', nextMeeting: '2026-05-07', stance: 'Hawkish Hold' },
  { bank: 'ECB', rate: '4.50%', lastAction: 'Hold', lastDate: '2026-03-06', nextMeeting: '2026-04-17', stance: 'Data Dependent' },
  { bank: 'Bank of Japan', rate: '0.25%', lastAction: '+25 bps', lastDate: '2026-03-14', nextMeeting: '2026-04-25', stance: 'Hawkish Shift' },
  { bank: 'Bank of England', rate: '5.25%', lastAction: 'Hold', lastDate: '2026-03-20', nextMeeting: '2026-05-09', stance: 'Dovish Hold' },
];

const fedDotPlot = [
  { year: '2026', median: 4.625, range: '4.375 - 5.125', cuts: 3 },
  { year: '2027', median: 3.625, range: '3.125 - 4.375', cuts: 4 },
  { year: 'Long Run', median: 2.750, range: '2.500 - 3.250', cuts: 0 },
];

const marketPricing = [
  { meeting: 'May 2026', prob25Cut: 18, probHold: 72, prob25Hike: 10, impliedRate: '5.30%' },
  { meeting: 'Jun 2026', prob25Cut: 42, probHold: 48, prob25Hike: 10, impliedRate: '5.18%' },
  { meeting: 'Jul 2026', prob25Cut: 55, probHold: 35, prob25Hike: 10, impliedRate: '5.05%' },
  { meeting: 'Sep 2026', prob25Cut: 68, probHold: 25, prob25Hike: 7, impliedRate: '4.88%' },
  { meeting: 'Dec 2026', prob25Cut: 78, probHold: 18, prob25Hike: 4, impliedRate: '4.62%' },
];

function stanceColor(stance: string): string {
  if (stance.includes('Hawkish')) return 'var(--color-signal-negative)';
  if (stance.includes('Dovish')) return 'var(--color-signal-positive)';
  return 'var(--color-signal-warning)';
}

// --- FedRateHistory data (20 data points over 5 years) -----------------------

const fedRateData: FedRatePoint[] = [
  { date: '2021-03', rate: 0.125, decision: 'HOLD' },
  { date: '2021-06', rate: 0.125, decision: 'HOLD' },
  { date: '2021-09', rate: 0.125, decision: 'HOLD' },
  { date: '2021-12', rate: 0.125, decision: 'HOLD' },
  { date: '2022-03', rate: 0.375, decision: 'HIKE' },
  { date: '2022-05', rate: 0.875, decision: 'HIKE' },
  { date: '2022-06', rate: 1.625, decision: 'HIKE' },
  { date: '2022-09', rate: 3.125, decision: 'HIKE' },
  { date: '2022-11', rate: 3.875, decision: 'HIKE' },
  { date: '2022-12', rate: 4.375, decision: 'HIKE' },
  { date: '2023-02', rate: 4.625, decision: 'HIKE' },
  { date: '2023-03', rate: 4.875, decision: 'HIKE' },
  { date: '2023-05', rate: 5.125, decision: 'HIKE' },
  { date: '2023-07', rate: 5.375, decision: 'HIKE' },
  { date: '2023-09', rate: 5.375, decision: 'HOLD' },
  { date: '2024-03', rate: 5.375, decision: 'HOLD' },
  { date: '2024-09', rate: 5.375, decision: 'HOLD' },
  { date: '2025-03', rate: 5.375, decision: 'HOLD' },
  { date: '2025-09', rate: 5.375, decision: 'HOLD' },
  { date: '2026-03', rate: 5.375, decision: 'HOLD' },
];

// --- MacroIndicatorTable data for recent releases ----------------------------

const recentReleases: MacroIndicator[] = [
  { name: 'CPI YoY', actual: 3.1, prior: 3.4, forecast: 3.2, surprise: -0.1, releaseDate: '2026-03-12' },
  { name: 'Core PCE YoY', actual: 2.8, prior: 2.8, forecast: 2.8, surprise: 0.0, releaseDate: '2026-03-28' },
  { name: 'NFP (000s)', actual: 275, prior: 229, forecast: 198, surprise: 77, releaseDate: '2026-03-07' },
  { name: 'GDP (QoQ SAAR)', actual: 2.4, prior: 3.2, forecast: 2.5, surprise: -0.1, releaseDate: '2026-03-27' },
  { name: 'Retail Sales MoM', actual: 0.6, prior: -0.8, forecast: 0.3, surprise: 0.3, releaseDate: '2026-03-14' },
];

// --- Component ---------------------------------------------------------------

export default function CentralBankMonitor() {
  const { data: apiCentralBanks } = useCentralBanks() as { data: any };
  const { data: apiMacro } = useMacroDashboardData() as { data: any };

  const activeBanks = (apiCentralBanks as any)?.banks ?? centralBanks;
  const activeDotPlot = (apiCentralBanks as any)?.dotPlot ?? fedDotPlot;
  const activePricing = (apiCentralBanks as any)?.marketPricing ?? marketPricing;
  const activeRateData = (apiCentralBanks as any)?.rateHistory ?? fedRateData;
  const activeReleases = (apiMacro as any)?.releases ?? recentReleases;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Central Bank Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Policy rates, meeting calendar, forward guidance, and market pricing</p>
      </div>

      {/* Central Bank Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeBanks.map((cb) => (
          <div key={cb.bank} style={panelStyle}>
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>{cb.bank}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '8px' }}>{cb.rate}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={labelStyle}>Last Action</span>
              <span style={{ ...dataStyle, fontSize: 'var(--text-sm)' }}>{cb.lastAction}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={labelStyle}>Next Meeting</span>
              <span style={{ ...dataStyle, fontSize: 'var(--text-sm)' }}>{cb.nextMeeting}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={labelStyle}>Stance</span>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: stanceColor(cb.stance) }}>{cb.stance}</span>
            </div>
          </div>
        ))}
      </div>

      {/* FedRateHistory Chart */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Fed Funds Rate History (5Y)</h2>
        <FedRateHistory data={activeRateData} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Fed Dot Plot Summary */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Fed Dot Plot Summary</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Year', 'Median Rate', 'Range', 'Implied Cuts'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Year' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeDotPlot.map((d) => (
                <tr key={d.year} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.year}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{d.median.toFixed(3)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{d.range}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.cuts > 0 ? 'var(--color-signal-positive)' : 'var(--color-text-secondary)' }}>{d.cuts > 0 ? d.cuts : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Fed Funds Futures */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Market-Implied Rate Path</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Meeting', 'Cut %', 'Hold %', 'Hike %', 'Implied'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Meeting' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activePricing.map((m) => (
                <tr key={m.meeting} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{m.meeting}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)' }}>{m.prob25Cut}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{m.probHold}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{m.prob25Hike}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{m.impliedRate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* MacroIndicatorTable for recent releases */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Recent Economic Releases</h2>
          <MacroIndicatorTable indicators={activeReleases} />
        </div>
      </div>
    </div>
  );
}
