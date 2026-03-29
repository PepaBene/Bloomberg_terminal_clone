// ---------------------------------------------------------------------------
// Bond Detail — Characteristics, Pricing, Yield Analysis, Call Schedule
// ---------------------------------------------------------------------------
import { BondTermsPanel, SpreadHistoryChart } from '@/components/fi';
import type { BondTerms, SpreadDataPoint } from '@/components/fi';

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

const bond = {
  issuer: 'Apple Inc.',
  cusip: '037833DX3',
  coupon: '3.250%',
  maturity: '2029-02-23',
  rating: 'AA+ / Aaa',
  issueSize: '$2,000M',
  currency: 'USD',
  seniority: 'Senior Unsecured',
  couponFreq: 'Semi-Annual',
};

const pricing = [
  { label: 'Price', value: '101.450' },
  { label: 'Yield (YTM)', value: '2.872%' },
  { label: 'Yield (YTW)', value: '2.845%' },
  { label: 'OAS', value: '42 bps' },
  { label: 'Z-Spread', value: '48 bps' },
  { label: 'Modified Duration', value: '2.78' },
  { label: 'Convexity', value: '0.09' },
  { label: 'DV01', value: '$0.0278' },
];

const comparables = [
  { issuer: 'MSFT 3.125% 2028', price: 100.82, ytm: 2.712, oas: 35, rating: 'AAA/Aaa' },
  { issuer: 'GOOGL 3.375% 2029', price: 101.10, ytm: 2.945, oas: 47, rating: 'AA+/Aa2' },
  { issuer: 'AMZN 3.600% 2029', price: 101.95, ytm: 3.015, oas: 52, rating: 'AA/Aa3' },
];

// --- BondTermsPanel data -----------------------------------------------------

const bondTerms: BondTerms = {
  cusip: '037833DX3',
  isin: 'US037833DX30',
  coupon: 3.25,
  frequency: 'Semi-Annual',
  maturity: '2029-02-23',
  issuer: 'Apple Inc.',
  rating: 'AA+ / Aaa',
  callSchedule: [
    { date: '2028-11-23', price: 100.25 },
    { date: '2029-01-23', price: 100.00 },
  ],
  covenants: [
    { type: 'Negative Pledge', description: 'Limitation on liens on principal property', status: 'Active' },
    { type: 'Change of Control', description: 'Put at 101 upon change of control', status: 'Active' },
  ],
};

// --- SpreadHistoryChart data for this bond -----------------------------------

function generateBondSpreadHistory(): SpreadDataPoint[] {
  const data: SpreadDataPoint[] = [];
  let oas = 58;
  const start = new Date('2025-03-28');
  for (let i = 0; i < 252; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const day = d.getDay();
    if (day === 0 || day === 6) continue;
    oas += (Math.random() - 0.52) * 2;
    oas = Math.max(25, Math.min(75, oas));
    data.push({ date: d.toISOString().slice(0, 10), oas: Math.round(oas * 10) / 10 });
  }
  return data;
}

const bondSpreadHistory = generateBondSpreadHistory();

// --- Component ---------------------------------------------------------------

export default function BondDetail() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {bond.issuer} {bond.coupon} {bond.maturity.slice(0, 4)}
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>CUSIP: {bond.cusip} &mdash; {bond.rating} &mdash; {bond.seniority}</p>
      </div>

      {/* Pricing KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {pricing.slice(0, 4).map((p) => (
          <div key={p.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{p.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{p.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* BondTermsPanel replaces inline bond characteristics */}
        <BondTermsPanel bond={bondTerms} />

        {/* Risk Analytics */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Analytics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {pricing.slice(4).map((p) => (
                <tr key={p.label} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.label}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* SpreadHistoryChart for this bond */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Spread History (12M)</h2>
          <SpreadHistoryChart data={bondSpreadHistory} benchmarkSpread={42} height={220} />
        </div>

        {/* Comparable Bonds */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Comparable Bonds</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Bond', 'Price', 'YTM', 'OAS', 'Rating'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Bond' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparables.map((c) => (
                <tr key={c.issuer} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.price.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.ytm.toFixed(3)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.oas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{c.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
