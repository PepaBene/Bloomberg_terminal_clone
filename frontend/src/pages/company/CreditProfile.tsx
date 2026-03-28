// ---------------------------------------------------------------------------
// Credit Profile — Ratings, Spread History, Debt Maturity, Covenants
// ---------------------------------------------------------------------------
import { CreditRatioPanel } from '@/components/company/CreditRatioPanel';
import { BondInventoryTable } from '@/components/company/BondInventoryTable';
import { MaturityWallChart } from '@/components/company/MaturityWallChart';
import { EquityCreditDivergence } from '@/components/company/EquityCreditDivergence';
import type { CreditRatio } from '@/components/company/CreditRatioPanel';
import type { BondRecord } from '@/components/company/BondInventoryTable';
import type { MaturityBucket } from '@/components/company/MaturityWallChart';
import type { EquityCreditPoint } from '@/components/company/EquityCreditDivergence';

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

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const ratings = [
  { agency: 'Moody\'s', rating: 'Aaa', outlook: 'Stable', lastAction: '2024-09-15' },
  { agency: 'S&P', rating: 'AA+', outlook: 'Stable', lastAction: '2024-07-22' },
  { agency: 'Fitch', rating: 'AA+', outlook: 'Stable', lastAction: '2024-08-10' },
];

const spreadHistory = [
  { date: '2026-03-27', spread: 42, zSpread: 48, asw: 45 },
  { date: '2026-02-27', spread: 45, zSpread: 51, asw: 48 },
  { date: '2026-01-27', spread: 50, zSpread: 56, asw: 53 },
  { date: '2025-12-27', spread: 47, zSpread: 53, asw: 50 },
  { date: '2025-09-27', spread: 55, zSpread: 61, asw: 58 },
];

const covenants = [
  { covenant: 'Debt / EBITDA Max', threshold: '4.0x', current: '0.4x', headroom: '3.6x', status: 'Pass' },
  { covenant: 'Interest Coverage Min', threshold: '3.0x', current: '29.3x', headroom: '26.3x', status: 'Pass' },
  { covenant: 'Secured Debt Limit', threshold: '$20.0B', current: '$0.0B', headroom: '$20.0B', status: 'Pass' },
  { covenant: 'Restricted Payments', threshold: 'Builder basket', current: 'N/A', headroom: 'N/A', status: 'Pass' },
];

const creditMetrics = [
  { label: 'Total Debt', value: '$105.2B' },
  { label: 'Net Debt', value: '$48.6B' },
  { label: 'LTM EBITDA', value: '$130.8B' },
  { label: 'Net Leverage', value: '0.37x' },
  { label: 'FCF / Debt', value: '98.2%' },
  { label: 'CDS 5Y', value: '32 bps' },
];

// CreditRatioPanel mock data
const leverageRatios: CreditRatio[] = [
  { name: 'Debt / EBITDA', value: 0.80, peerMedian: 1.50, trend: 'improving' },
  { name: 'Net Debt / EBITDA', value: 0.37, peerMedian: 1.10, trend: 'stable' },
  { name: 'Debt / Equity', value: 1.42, peerMedian: 0.85, trend: 'stable' },
  { name: 'Debt / Capital', value: 0.59, peerMedian: 0.45, trend: 'stable' },
];

const coverageRatios: CreditRatio[] = [
  { name: 'Interest Coverage', value: 29.30, peerMedian: 12.50, trend: 'improving' },
  { name: 'EBITDA / Interest', value: 33.40, peerMedian: 14.00, trend: 'improving' },
  { name: 'FCF / Debt', value: 0.98, peerMedian: 0.35, trend: 'stable' },
];

const liquidityRatios: CreditRatio[] = [
  { name: 'Current Ratio', value: 0.99, peerMedian: 1.50, trend: 'deteriorating' },
  { name: 'Quick Ratio', value: 0.94, peerMedian: 1.20, trend: 'deteriorating' },
  { name: 'Cash / ST Debt', value: 1.89, peerMedian: 2.50, trend: 'stable' },
];

// BondInventoryTable mock data
const bondInventory: BondRecord[] = [
  { cusip: '037833DL5', coupon: 2.050, maturity: '2026-09-11', outstanding: 3500000000, rating: 'AA+', spread: 38, price: 99.125, ytm: 2.180 },
  { cusip: '037833DM3', coupon: 2.375, maturity: '2027-02-08', outstanding: 2750000000, rating: 'AA+', spread: 42, price: 98.750, ytm: 2.540 },
  { cusip: '037833DN1', coupon: 2.850, maturity: '2028-05-11', outstanding: 4000000000, rating: 'AA+', spread: 48, price: 97.875, ytm: 3.100 },
  { cusip: '037833DP6', coupon: 3.000, maturity: '2029-06-20', outstanding: 3200000000, rating: 'AA+', spread: 52, price: 97.250, ytm: 3.320 },
  { cusip: '037833DQ4', coupon: 3.250, maturity: '2031-02-23', outstanding: 5500000000, rating: 'AA+', spread: 58, price: 96.500, ytm: 3.580 },
  { cusip: '037833DR2', coupon: 3.450, maturity: '2033-05-06', outstanding: 4800000000, rating: 'AA+', spread: 65, price: 95.750, ytm: 3.780 },
  { cusip: '037833DS0', coupon: 4.100, maturity: '2042-08-08', outstanding: 6200000000, rating: 'AA+', spread: 78, price: 93.125, ytm: 4.520 },
  { cusip: '037833DT8', coupon: 4.375, maturity: '2052-11-15', outstanding: 5000000000, rating: 'AA+', spread: 85, price: 91.500, ytm: 4.850 },
];

// MaturityWallChart mock data
const maturityWall: MaturityBucket[] = [
  { year: 2026, amount: 8500 },
  { year: 2027, amount: 11200 },
  { year: 2028, amount: 9800 },
  { year: 2029, amount: 7400 },
  { year: 2030, amount: 5600 },
  { year: 2031, amount: 12300 },
  { year: 2032, amount: 4200 },
  { year: 2033, amount: 8900 },
  { year: 2034, amount: 3100 },
  { year: 2035, amount: 6500 },
];

// EquityCreditDivergence mock data
const equityCreditData: EquityCreditPoint[] = [
  { date: '2025-04', price: 170.50, spread: 58 },
  { date: '2025-05', price: 172.30, spread: 55 },
  { date: '2025-06', price: 168.90, spread: 60 },
  { date: '2025-07', price: 175.10, spread: 52 },
  { date: '2025-08', price: 178.40, spread: 50 },
  { date: '2025-09', price: 171.20, spread: 55 },
  { date: '2025-10', price: 174.60, spread: 53 },
  { date: '2025-11', price: 180.30, spread: 48 },
  { date: '2025-12', price: 176.80, spread: 47 },
  { date: '2026-01', price: 173.50, spread: 50 },
  { date: '2026-02', price: 177.90, spread: 45 },
  { date: '2026-03', price: 178.72, spread: 42 },
];

// --- Component ---------------------------------------------------------------

export default function CreditProfile() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Credit Profile
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {creditMetrics.map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Credit Ratio Panels — Leverage, Coverage, Liquidity */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        <CreditRatioPanel ratios={leverageRatios} category="leverage" />
        <CreditRatioPanel ratios={coverageRatios} category="coverage" />
        <CreditRatioPanel ratios={liquidityRatios} category="liquidity" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start', marginBottom: 'var(--panel-gap)' }}>
        {/* Credit Ratings */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Credit Ratings</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Agency', 'Rating', 'Outlook', 'Last Action'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ratings.map((r) => (
                <tr key={r.agency} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.agency}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{r.rating}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)' }}>{r.outlook}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.lastAction}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Spread History */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Spread History (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'OAS', 'Z-Spread', 'ASW'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spreadHistory.map((s) => (
                <tr key={s.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{s.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.zSpread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.asw}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Maturity Wall Chart */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <MaturityWallChart maturities={maturityWall} totalDebt={105200} height={280} />
      </div>

      {/* Bond Inventory Table */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <BondInventoryTable bonds={bondInventory} />
      </div>

      {/* Equity vs Credit Divergence */}
      <EquityCreditDivergence data={equityCreditData} entityName={company.name} height={300} />

      {/* Covenant Analysis */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Covenant Analysis</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Covenant', 'Threshold', 'Current', 'Headroom', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Covenant' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {covenants.map((c) => (
              <tr key={c.covenant} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.covenant}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.threshold}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.current}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.headroom}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-positive)', fontWeight: 500 }}>{c.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
