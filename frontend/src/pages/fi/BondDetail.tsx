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

// --- Default empty data (populated by API) -----------------------------------

const bond = {
  issuer: '',
  cusip: '',
  coupon: '',
  maturity: '',
  rating: '',
  issueSize: '',
  currency: 'USD',
  seniority: '',
  couponFreq: '',
};

const pricing: { label: string; value: string }[] = [];

const comparables: { issuer: string; price: number; ytm: number; oas: number; rating: string }[] = [];

const bondTerms: BondTerms = {
  cusip: '',
  isin: '',
  coupon: 0,
  frequency: '',
  maturity: '',
  issuer: '',
  rating: '',
  callSchedule: [],
  covenants: [],
};

const bondSpreadHistory: SpreadDataPoint[] = [];

// --- Component ---------------------------------------------------------------

export default function BondDetail() {
  const { cusip } = useParams<{ cusip: string }>();
  const resolvedCusip = cusip ?? '';

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

  const cashFlows = (apiCashFlows as any[]) ?? [];

  // Duration / Convexity / OAS KPI data from API with mock fallbacks
  const durationKpis = [
    { label: 'Modified Duration', value: (apiBondDetail as any)?.modifiedDuration ?? '—' },
    { label: 'Effective Duration', value: (apiBondDetail as any)?.effectiveDuration ?? '—' },
    { label: 'Convexity', value: (apiBondDetail as any)?.convexity ?? '—' },
    { label: 'OAS', value: (apiBondDetail as any)?.oas ?? '—' },
    { label: 'Z-Spread', value: (apiBondDetail as any)?.zSpread ?? '—' },
    { label: 'DV01', value: (apiBondDetail as any)?.dv01 ?? '—' },
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
