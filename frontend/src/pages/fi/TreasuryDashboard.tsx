// ---------------------------------------------------------------------------
// Treasury Dashboard — Yield Curve, Auction Results, Rate Sensitivity
// ---------------------------------------------------------------------------
import { TreasuryAuctionCalendar } from '@/components/fi';
import type { AuctionRecord } from '@/components/fi';
import { EmptyState } from '@/components/feedback';
import {
  useYieldCurve,
  useYieldCurveSpreads,
  useTreasuryAuction,
  useTreasuriesOnTheRun,
  useYieldCurveForward,
  useRealYieldCurve,
  useBreakevenCurve,
  useMoneyMarketRates,
} from '@/hooks';

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

function chgColor(v: number): string {
  return v >= 0 ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)';
}

// --- Mock Data ---------------------------------------------------------------

const curveData = [
  { tenor: '1M', yield: 5.31, chg: -0.01 },
  { tenor: '3M', yield: 5.28, chg: -0.02 },
  { tenor: '6M', yield: 5.12, chg: -0.03 },
  { tenor: '1Y', yield: 4.85, chg: -0.05 },
  { tenor: '2Y', yield: 4.52, chg: -0.04 },
  { tenor: '5Y', yield: 4.18, chg: -0.03 },
  { tenor: '10Y', yield: 4.28, chg: -0.03 },
  { tenor: '30Y', yield: 4.52, chg: -0.02 },
];

const keySpreads = [
  { label: '2s10s', value: -24, chg: 1 },
  { label: '2s30s', value: 0, chg: 2 },
  { label: '5s30s', value: 34, chg: 1 },
  { label: '10Y TIPS BE', value: 2.32, chg: -0.01 },
  { label: '10Y Real', value: 1.96, chg: -0.02 },
  { label: 'Fed Funds', value: 5.33, chg: 0 },
];

const rateSensitivity = [
  { scenario: '+100 bps parallel', duration: -6.2, convexity: 0.3, pnl: '-$6.2M' },
  { scenario: '-100 bps parallel', duration: 6.2, convexity: 0.3, pnl: '+$6.5M' },
  { scenario: 'Bear steepener', duration: -2.1, convexity: 0.1, pnl: '-$2.0M' },
  { scenario: 'Bull flattener', duration: 3.8, convexity: 0.2, pnl: '+$4.0M' },
];

// --- TreasuryAuctionCalendar data (5 upcoming + 5 completed) ----------------

const auctionRecords: AuctionRecord[] = [
  { date: '2026-04-02', security: '3Y Note',  size: '$46B', status: 'upcoming' },
  { date: '2026-04-03', security: '10Y Note', size: '$38B', status: 'upcoming' },
  { date: '2026-04-04', security: '30Y Bond', size: '$22B', status: 'upcoming' },
  { date: '2026-04-08', security: '2Y Note',  size: '$50B', status: 'upcoming' },
  { date: '2026-04-09', security: '5Y Note',  size: '$49B', status: 'upcoming' },
  { date: '2026-03-27', security: '7Y Note',  size: '$41B', bidToCover: 2.52, tailBps: 0.5, status: 'completed' },
  { date: '2026-03-26', security: '5Y Note',  size: '$49B', bidToCover: 2.45, tailBps: -0.1, status: 'completed' },
  { date: '2026-03-25', security: '2Y Note',  size: '$48B', bidToCover: 2.68, tailBps: 0.2, status: 'completed' },
  { date: '2026-03-20', security: '20Y Bond', size: '$16B', bidToCover: 2.38, tailBps: 1.2, status: 'completed' },
  { date: '2026-03-18', security: '10Y Note', size: '$39B', bidToCover: 2.56, tailBps: 0.3, status: 'completed' },
];

const forwardCurveData = [
  { horizon: '1Y Forward', rate2Y: 4.15, rate5Y: 3.95, rate10Y: 4.10 },
  { horizon: '2Y Forward', rate2Y: 3.85, rate5Y: 3.78, rate10Y: 4.02 },
  { horizon: '5Y Forward', rate2Y: 3.52, rate5Y: 3.60, rate10Y: 3.88 },
];

const realYieldData = [
  { tenor: '5Y', realYield: 1.82, chg: -0.02 },
  { tenor: '10Y', realYield: 1.96, chg: -0.03 },
  { tenor: '30Y', realYield: 2.12, chg: -0.01 },
];

const breakevenData = [
  { tenor: '5Y', breakeven: 2.36, chg: 0.01 },
  { tenor: '10Y', breakeven: 2.32, chg: -0.01 },
  { tenor: '30Y', breakeven: 2.40, chg: 0.02 },
];

const moneyMarketRates = [
  { name: 'SOFR', rate: 5.31, chg: 0.00 },
  { name: 'EFFR', rate: 5.33, chg: 0.00 },
  { name: 'Repo (O/N)', rate: 5.30, chg: -0.01 },
  { name: '3M T-Bill', rate: 5.28, chg: -0.02 },
  { name: '6M T-Bill', rate: 5.12, chg: -0.03 },
  { name: 'Commercial Paper (A1/P1)', rate: 5.35, chg: 0.01 },
];

// --- Component ---------------------------------------------------------------

export default function TreasuryDashboard() {
  const { data: apiCurve } = useYieldCurve();
  const { data: apiSpreads } = useYieldCurveSpreads();
  const { data: apiAuctions } = useTreasuryAuction();
  useTreasuriesOnTheRun();
  const { data: apiForward } = useYieldCurveForward();
  const { data: apiReal } = useRealYieldCurve();
  const { data: apiBreakeven } = useBreakevenCurve();
  const { data: apiMoneyMarket } = useMoneyMarketRates();

  const activeCurve = (apiCurve as any[]) ?? curveData;
  const activeSpreads = (apiSpreads as any[]) ?? keySpreads;
  const activeAuctions = (apiAuctions as any[]) ?? auctionRecords;
  const activeForward = (apiForward as any[]) ?? forwardCurveData;
  const activeReal = (apiReal as any[]) ?? realYieldData;
  const activeBreakeven = (apiBreakeven as any[]) ?? breakevenData;
  const activeMoneyMarket = (apiMoneyMarket as any[]) ?? moneyMarketRates;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Treasury Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>UST curve, key spreads, auction results, and rate sensitivity</p>
      </div>

      {/* Key Spreads KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeSpreads.map((s: any) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              {typeof s.value === 'number' && s.value % 1 === 0 ? `${s.value} bps` : `${s.value}%`}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Treasury Curve */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Treasury Yield Curve</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Tenor', 'Yield', 'Chg (bps)'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeCurve.map((c: any) => (
                <tr key={c.tenor} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.yield.toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(c.chg) }}>
                    {c.chg > 0 ? '+' : ''}{(c.chg * 100).toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Rate Sensitivity */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Rate Sensitivity Analysis</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Scenario', 'Duration', 'Convexity', 'P&L Impact'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Scenario' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rateSensitivity.map((r) => (
                <tr key={r.scenario} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.scenario}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.duration.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.convexity.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: r.pnl.startsWith('+') ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{r.pnl}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* TreasuryAuctionCalendar Component */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Auction Calendar</h2>
          <TreasuryAuctionCalendar auctions={activeAuctions} />
        </div>

        {/* 10Y OAS history — no index-level Treasury OAS series endpoint exists;
            honest empty state rather than a fabricated random walk (§8.3). */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>10Y Spread History</h2>
          <EmptyState
            icon="📊"
            title="Spread series unavailable"
            description="No index-level 10Y Treasury OAS time series is wired to this deployment."
          />
        </div>

        {/* Forward Curve */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Forward Curve</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Horizon', '2Y Rate', '5Y Rate', '10Y Rate'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Horizon' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeForward.map((f: any) => (
                <tr key={f.horizon} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.horizon}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{Number(f.rate2Y).toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{Number(f.rate5Y).toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{Number(f.rate10Y).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Real vs Breakeven Yields */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Real vs Breakeven Yields</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Tenor', 'Real Yield', 'Chg', 'Breakeven', 'Chg'].map((h, i) => (
                  <th key={`${h}-${i}`} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeReal.map((r: any, idx: number) => {
                const b = activeBreakeven[idx] as any;
                return (
                  <tr key={r.tenor} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.tenor}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{Number(r.realYield).toFixed(2)}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(r.chg) }}>
                      {r.chg > 0 ? '+' : ''}{(r.chg * 100).toFixed(1)}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{b ? `${Number(b.breakeven).toFixed(2)}%` : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: b ? chgColor(b.chg) : 'inherit' }}>
                      {b ? `${b.chg > 0 ? '+' : ''}${(b.chg * 100).toFixed(1)}` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Money Market Rates */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Money Market Rates</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Instrument', 'Rate', 'Chg (bps)'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Instrument' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeMoneyMarket.map((m: any) => (
                <tr key={m.name} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{m.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{Number(m.rate).toFixed(2)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(m.chg) }}>
                    {m.chg > 0 ? '+' : ''}{(m.chg * 100).toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
