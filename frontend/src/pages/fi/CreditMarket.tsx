// ---------------------------------------------------------------------------
// Credit Market — IG/HY Spread Indices, Credit Regime, Sector Spreads
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { KeySpreadsPanel, SpreadHistoryChart } from '@/components/fi';
import type { SpreadRow, SpreadDataPoint } from '@/components/fi';
import { EmptyState } from '@/components/feedback';
import { useCreditSpreads, useDistressedCredit, useFIIndices, useFIBriefing } from '@/hooks';

// ICE BofA US Corporate Master OAS — the canonical IG series ingested by
// fred_credit_spreads.py (rating_category "IG").
const IG_OAS_SERIES = 'BAMLC0A0CM';

interface CreditSpreadObsDTO {
  observation_date: string;
  spread_bps?: number | null;
}
interface PaginatedSpreads { data: CreditSpreadObsDTO[] }

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
  return v <= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const spreadIndices = [
  { index: 'CDX IG', spread: 52, chg1d: -1, chg1w: -3, chg1m: -8, pctile: 22 },
  { index: 'CDX HY', spread: 328, chg1d: 2, chg1w: -5, chg1m: -18, pctile: 35 },
  { index: 'iTraxx Main', spread: 55, chg1d: 0, chg1w: -2, chg1m: -6, pctile: 25 },
  { index: 'iTraxx Xover', spread: 295, chg1d: -3, chg1w: -8, chg1m: -22, pctile: 30 },
];

const creditRegime = [
  { label: 'Current Regime', value: 'Risk-On' },
  { label: 'IG Spread Pctile (5Y)', value: '22nd' },
  { label: 'HY Spread Pctile (5Y)', value: '35th' },
  { label: 'IG Default Rate (LTM)', value: '0.05%' },
  { label: 'HY Default Rate (LTM)', value: '2.8%' },
  { label: 'Distressed Ratio', value: '4.2%' },
];

const sectorSpreads = [
  { sector: 'Technology', igOas: 45, hyOas: 285, chg1m: -12 },
  { sector: 'Healthcare', igOas: 62, hyOas: 310, chg1m: -8 },
  { sector: 'Financials', igOas: 58, hyOas: 295, chg1m: -5 },
  { sector: 'Energy', igOas: 72, hyOas: 365, chg1m: 8 },
  { sector: 'Consumer', igOas: 55, hyOas: 305, chg1m: -10 },
  { sector: 'Industrials', igOas: 60, hyOas: 320, chg1m: -6 },
  { sector: 'Utilities', igOas: 68, hyOas: 275, chg1m: -3 },
];

// --- KeySpreadsPanel data for market-wide spreads ----------------------------

const marketSpreads: SpreadRow[] = [
  { name: 'CDX IG',       value: 52,  change1d: -1, change1w: -3, percentile: 22 },
  { name: 'CDX HY',       value: 328, change1d: 2,  change1w: -5, percentile: 35 },
  { name: 'iTraxx Main',  value: 55,  change1d: 0,  change1w: -2, percentile: 25 },
  { name: 'iTraxx Xover', value: 295, change1d: -3, change1w: -8, percentile: 30 },
];

// --- Component ---------------------------------------------------------------

export default function CreditMarket() {
  const { data: apiSpreads } = useCreditSpreads();
  const { data: apiDistressed } = useDistressedCredit();
  const { data: apiIndices } = useFIIndices();
  const { data: apiBriefing } = useFIBriefing();

  // IG OAS history — real FRED-sourced series (replaces the prior Math.random
  // walk). Ascending by date for the chart.
  const { data: igHistoryRaw, isLoading: loadingIgHistory } = useQuery({
    queryKey: ['fi', 'spreads', 'history', IG_OAS_SERIES],
    queryFn: () => api.get<PaginatedSpreads>('/v1/fixed-income/spreads/history', { series_id: IG_OAS_SERIES, page_size: 400 }),
    retry: 0,
  });
  const creditSpreadHistory: SpreadDataPoint[] = (igHistoryRaw?.data ?? [])
    .filter((o) => o.spread_bps != null)
    .map((o) => ({ date: o.observation_date, oas: Math.round(o.spread_bps as number) }))
    .sort((a, b) => a.date.localeCompare(b.date));
  const latestIgOas = creditSpreadHistory.length > 0 ? creditSpreadHistory[creditSpreadHistory.length - 1]!.oas : undefined;

  const indicesData = (apiIndices as any[]) ?? spreadIndices;
  const sectorsData = (apiSpreads as any)?.sectors ?? sectorSpreads;
  const regimeData = (apiSpreads as any)?.regime ?? creditRegime;

  const distressed = (apiDistressed as any[]) ?? [
    { issuer: 'Rite Aid Corp', rating: 'CCC', spread: 1850, defaultProb: 42.5 },
    { issuer: 'Community Health', rating: 'CCC+', spread: 1420, defaultProb: 28.8 },
    { issuer: 'Carvana Co', rating: 'CCC', spread: 1680, defaultProb: 35.2 },
  ];

  const briefingText = (apiBriefing as any)?.text ??
    'Investment-grade spreads remain well-contained at 92bps, reflecting continued demand for quality credit amid a stable macro backdrop. High-yield markets are constructive with the distressed ratio holding near cycle lows at 4.2%. Sector rotation favors Technology and Consumer credits while Energy spreads face headwinds from recent commodity volatility.';

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Credit Market Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>IG &amp; HY spread indices, credit regime, and sector analysis</p>
      </div>

      {/* Regime KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {regimeData.map((r: any) => (
          <div key={r.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{r.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: r.value === 'Risk-On' ? 'var(--color-signal-positive)' : 'var(--color-text-primary)' }}>{r.value}</div>
          </div>
        ))}
      </div>

      {/* KeySpreadsPanel for market-wide spreads */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Market-Wide Key Spreads</h2>
        <KeySpreadsPanel spreads={marketSpreads} />
      </div>

      {/* SpreadHistoryChart for IG index — real ICE BofA US Corporate OAS */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>IG Corporate OAS History</h2>
        {loadingIgHistory ? (
          <EmptyState icon="⏳" title="Loading spread history…" />
        ) : creditSpreadHistory.length === 0 ? (
          <EmptyState icon="📉" title="No spread history" description="Credit-spread ingestion (FRED) has not populated this series yet." />
        ) : (
          <SpreadHistoryChart data={creditSpreadHistory} benchmarkSpread={latestIgOas} height={220} />
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Spread Indices */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Credit Indices (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Index', 'Spread', '1D', '1W', '1M', 'Pctile'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Index' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {indicesData.map((s: any) => (
                <tr key={s.index} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.index}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{s.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1d) }}>{s.chg1d > 0 ? '+' : ''}{s.chg1d}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1w) }}>{s.chg1w > 0 ? '+' : ''}{s.chg1w}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1m) }}>{s.chg1m > 0 ? '+' : ''}{s.chg1m}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{s.pctile}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Sector Spreads */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Sector Spreads (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Sector', 'IG OAS', 'HY OAS', '1M Chg'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Sector' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sectorsData.map((s: any) => (
                <tr key={s.sector} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sector}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.igOas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.hyOas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1m) }}>{s.chg1m > 0 ? '+' : ''}{s.chg1m}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Distressed Credits */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Distressed Credits</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Issuer', 'Rating', 'Spread', 'Prob Default %'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {distressed.map((d: any) => (
              <tr key={d.issuer} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.issuer}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{d.rating}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.spread}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-negative)' }}>{d.defaultProb}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* AI Credit Briefing */}
      {(apiBriefing || briefingText) && (
        <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
          <h2 style={sectionTitle}>AI Credit Briefing</h2>
          <p style={{ ...labelStyle, fontSize: 'var(--text-base)', lineHeight: 1.6, margin: 0 }}>{briefingText}</p>
        </div>
      )}
    </div>
  );
}
