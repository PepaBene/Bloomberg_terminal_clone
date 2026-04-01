// ---------------------------------------------------------------------------
// Bond Detail — Characteristics, Pricing, Yield Analysis, Call Schedule
// ---------------------------------------------------------------------------
import { useParams } from 'react-router-dom';
import { BondTermsPanel, SpreadHistoryChart } from '@/components/fi';
import type { BondTerms, SpreadDataPoint } from '@/components/fi';
import {
  useBondDetail,
  useBondPrices,
  useBondSpreads,
  useBondCashFlows,
  useBondCallSchedule,
  useBondCovenants,
  useBondComparables,
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
  const { cusip } = useParams<{ cusip: string }>();
  const resolvedCusip = cusip ?? '037833DX3';

  // --- API hooks with mock fallbacks ---
  const { data: apiBondDetail } = useBondDetail(resolvedCusip);
  const { data: apiBondPrices } = useBondPrices(resolvedCusip);
  const { data: apiBondSpreads } = useBondSpreads(resolvedCusip);
  const { data: apiCashFlows } = useBondCashFlows(resolvedCusip);
  const { data: apiCallSchedule } = useBondCallSchedule(resolvedCusip);
  const { data: apiCovenants } = useBondCovenants(resolvedCusip);
  const { data: apiComparables } = useBondComparables(resolvedCusip);

  // Resolve data with mock fallbacks
  const bondData = (apiBondDetail as typeof bond | undefined) ?? bond;
  const pricingData = (apiBondPrices as typeof pricing | undefined) ?? pricing;
  const spreadsData = (apiBondSpreads as SpreadDataPoint[] | undefined) ?? bondSpreadHistory;
  const comparablesData = (apiComparables as typeof comparables | undefined) ?? comparables;

  const resolvedCallSchedule = (apiCallSchedule as typeof bondTerms.callSchedule | undefined) ?? bondTerms.callSchedule;
  const resolvedCovenants = (apiCovenants as typeof bondTerms.covenants | undefined) ?? bondTerms.covenants;

  const resolvedBondTerms: BondTerms = {
    ...bondTerms,
    cusip: bondData.cusip,
    coupon: typeof bondData.coupon === 'string' ? parseFloat(bondData.coupon) : bondData.coupon,
    maturity: bondData.maturity,
    issuer: bondData.issuer,
    rating: bondData.rating,
    callSchedule: resolvedCallSchedule,
    covenants: resolvedCovenants,
  };

  const cashFlows = (apiCashFlows as any[]) ?? [
    { date: '2026-08-23', principal: 0, interest: 16250, total: 16250 },
    { date: '2027-02-23', principal: 0, interest: 16250, total: 16250 },
    { date: '2027-08-23', principal: 0, interest: 16250, total: 16250 },
    { date: '2028-02-23', principal: 0, interest: 16250, total: 16250 },
    { date: '2029-02-23', principal: 1000000, interest: 16250, total: 1016250 },
  ];

  // Duration / Convexity / OAS KPI data from API with mock fallbacks
  const durationKpis = [
    { label: 'Modified Duration', value: (apiBondDetail as any)?.modifiedDuration ?? '2.78' },
    { label: 'Effective Duration', value: (apiBondDetail as any)?.effectiveDuration ?? '2.74' },
    { label: 'Convexity', value: (apiBondDetail as any)?.convexity ?? '0.09' },
    { label: 'OAS', value: (apiBondDetail as any)?.oas ?? '42 bps' },
    { label: 'Z-Spread', value: (apiBondDetail as any)?.zSpread ?? '48 bps' },
    { label: 'DV01', value: (apiBondDetail as any)?.dv01 ?? '$0.0278' },
  ];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {bondData.issuer} {bondData.coupon} {bondData.maturity.slice(0, 4)}
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>CUSIP: {bondData.cusip} &mdash; {bondData.rating} &mdash; {bondData.seniority}</p>
      </div>

      {/* Pricing KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {pricingData.slice(0, 4).map((p) => (
          <div key={p.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{p.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{p.value}</div>
          </div>
        ))}
      </div>

      {/* Duration / Convexity / OAS KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {durationKpis.map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* BondTermsPanel replaces inline bond characteristics */}
        <BondTermsPanel bond={resolvedBondTerms} />

        {/* Risk Analytics */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Analytics</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {pricingData.slice(4).map((p) => (
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
          <SpreadHistoryChart data={spreadsData} benchmarkSpread={42} height={220} />
        </div>

        {/* Cash Flows */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Cash Flows</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Principal', 'Interest', 'Total'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Date' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cashFlows.map((cf: any) => (
                <tr key={cf.date} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{cf.date}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{cf.principal.toLocaleString()}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{cf.interest.toLocaleString()}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{cf.total.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
              {comparablesData.map((c) => (
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
