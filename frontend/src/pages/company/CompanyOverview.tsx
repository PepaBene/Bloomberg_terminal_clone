// ---------------------------------------------------------------------------
// Company Overview — Main Company Analysis Page
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useSecurityStore } from '@/stores/securityContext';
import { CandlestickChart, BarChartComponent, GaugeChart, ScoreBreakdown } from '@/components/charts';
import type { CandlestickDataPoint, ScoreItem } from '@/components/charts';
import { KeyMetricsGrid } from '@/components/company/KeyMetricsGrid';
import type { MetricItem } from '@/components/company/KeyMetricsGrid';
import { SentimentGauge } from '@/components/intelligence';
import { useSentimentHistory, useEarningsSurprises, useTechnicalSignals, useCompositeScores } from '@/hooks';
import { TimeSeriesChart } from '@/components/charts';

// --- Helpers -----------------------------------------------------------------

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function formatM(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}B`;
  return `$${n.toFixed(0)}M`;
}

// --- Skeleton ----------------------------------------------------------------

function Skeleton({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-sm)',
      }}
    />
  );
}

// --- Mock Data (fallback) ----------------------------------------------------

interface CompanyInfo {
  name: string;
  ticker: string;
  exchange: string;
  sector: string;
  industry: string;
  price: number;
  changePct: number;
}

const MOCK_COMPANY: CompanyInfo = {
  name: 'Apple Inc.',
  ticker: 'AAPL',
  exchange: 'NASDAQ',
  sector: 'Information Technology',
  industry: 'Technology Hardware, Storage & Peripherals',
  price: 178.72,
  changePct: -0.34,
};

const MOCK_METRICS: MetricItem[] = [
  { label: 'Market Cap',    value: '$2.78T' },
  { label: 'P/E (TTM)',     value: '28.6x' },
  { label: 'EV/EBITDA',     value: '22.1x' },
  { label: 'Rev Growth',    value: '+5.2%', subValue: 'YoY', change: 5.2 },
  { label: 'ROE',           value: '156.8%' },
  { label: 'Div Yield',     value: '0.55%' },
];

interface QuarterlyFinancial {
  period: string;
  revenue: number;
  netIncome: number;
  ebitda: number;
  fcf: number;
  eps: number;
}

const MOCK_QUARTERLY: QuarterlyFinancial[] = [
  { period: 'Q1 2026', revenue: 119500, netIncome: 33916, ebitda: 43200, fcf: 32000, eps: 2.18 },
  { period: 'Q4 2025', revenue: 94930,  netIncome: 24780, ebitda: 32500, fcf: 25700, eps: 1.64 },
  { period: 'Q3 2025', revenue: 85777,  netIncome: 22956, ebitda: 28900, fcf: 24300, eps: 1.46 },
  { period: 'Q2 2025', revenue: 81797,  netIncome: 21448, ebitda: 27100, fcf: 24100, eps: 1.40 },
];

interface QualityScoreItem {
  name: string;
  value: number;
  maxValue: number;
  classification: string;
}

const MOCK_QUALITY: QualityScoreItem[] = [
  { name: 'Piotroski F-Score', value: 7, maxValue: 9, classification: 'Strong' },
  { name: 'Altman Z-Score',    value: 5.82, maxValue: 10, classification: 'Safe' },
  { name: 'Composite Quality', value: 82, maxValue: 100, classification: 'Excellent' },
];

// Piotroski sub-score breakdown
const PIOTROSKI_BREAKDOWN: ScoreItem[] = [
  { name: 'Positive Net Income', score: 1, max: 1 },
  { name: 'Positive Operating CF', score: 1, max: 1 },
  { name: 'ROA Increasing', score: 1, max: 1 },
  { name: 'CF > Net Income', score: 1, max: 1 },
  { name: 'Lower Leverage', score: 0, max: 1 },
  { name: 'Higher Current Ratio', score: 1, max: 1 },
  { name: 'No Dilution', score: 0, max: 1 },
  { name: 'Higher Gross Margin', score: 1, max: 1 },
  { name: 'Higher Asset Turnover', score: 1, max: 1 },
];

const ALTMAN_BREAKDOWN: ScoreItem[] = [
  { name: 'Working Capital / Assets', score: 1, max: 1, description: '0.12' },
  { name: 'Retained Earnings / Assets', score: 1, max: 1, description: '0.85' },
  { name: 'EBIT / Assets', score: 1, max: 1, description: '0.34' },
  { name: 'Mkt Cap / Total Liabilities', score: 1, max: 1, description: '9.82' },
  { name: 'Revenue / Assets', score: 1, max: 1, description: '1.11' },
];

const BENEISH_BREAKDOWN: ScoreItem[] = [
  { name: 'Days Sales in Receivables', score: 1, max: 1, description: '1.02' },
  { name: 'Gross Margin Index', score: 1, max: 1, description: '0.98' },
  { name: 'Asset Quality Index', score: 1, max: 1, description: '1.01' },
  { name: 'Sales Growth Index', score: 1, max: 1, description: '1.05' },
  { name: 'Depreciation Index', score: 0, max: 1, description: '1.15' },
  { name: 'SGA Index', score: 1, max: 1, description: '0.97' },
  { name: 'Leverage Index', score: 1, max: 1, description: '1.02' },
  { name: 'Total Accruals', score: 1, max: 1, description: '-0.04' },
];

interface NewsItem {
  id: string;
  headline: string;
  source: string;
  time: string;
}

const MOCK_NEWS: NewsItem[] = [
  { id: '1', headline: 'Apple Vision Pro sales exceed expectations in Q1', source: 'Bloomberg', time: '2h ago' },
  { id: '2', headline: 'Apple expands AI chip partnership with TSMC',      source: 'Reuters',   time: '4h ago' },
  { id: '3', headline: 'Services revenue hits record $24.2B in quarter',   source: 'CNBC',      time: '6h ago' },
  { id: '4', headline: 'Apple Car project timeline pushed to 2028',        source: 'WSJ',       time: '1d ago' },
  { id: '5', headline: 'App Store antitrust ruling appeal filed',          source: 'FT',        time: '1d ago' },
];

interface FilingItem {
  id: string;
  date: string;
  type: '10-K' | '10-Q' | '8-K';
  title: string;
}

const MOCK_FILINGS: FilingItem[] = [
  { id: 'f1', date: '2026-02-14', type: '10-K', title: 'Annual Report FY2025' },
  { id: 'f2', date: '2026-01-30', type: '8-K', title: 'Q1 2026 Earnings Release' },
  { id: 'f3', date: '2025-11-01', type: '10-Q', title: 'Quarterly Report Q4 2025' },
  { id: 'f4', date: '2025-10-15', type: '8-K', title: 'Executive Leadership Change' },
  { id: 'f5', date: '2025-08-02', type: '10-Q', title: 'Quarterly Report Q3 2025' },
];

const FILING_TYPE_COLORS: Record<string, string> = {
  '10-K': 'var(--color-accent-primary)',
  '10-Q': 'var(--color-text-secondary)',
  '8-K': 'var(--color-signal-warning)',
};

interface HolderItem {
  name: string;
  shares: string;
  pctOwnership: string;
}

const MOCK_HOLDERS: HolderItem[] = [
  { name: 'Vanguard Group', shares: '1.31B', pctOwnership: '8.51%' },
  { name: 'BlackRock Inc.', shares: '1.02B', pctOwnership: '6.63%' },
  { name: 'Berkshire Hathaway', shares: '905M', pctOwnership: '5.88%' },
  { name: 'State Street Corp.', shares: '591M', pctOwnership: '3.84%' },
  { name: 'FMR LLC (Fidelity)', shares: '350M', pctOwnership: '2.27%' },
];

// --- OHLC Mock Data (6 months daily) -----------------------------------------

function generateOHLC(): CandlestickDataPoint[] {
  const data: CandlestickDataPoint[] = [];
  let close = 175;
  const start = new Date('2025-09-27');
  for (let i = 0; i < 130; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const day = d.getDay();
    if (day === 0 || day === 6) continue;
    const change = (Math.random() - 0.48) * 3.5;
    const open = close;
    close = Math.round((open + change) * 100) / 100;
    const high = Math.round((Math.max(open, close) + Math.random() * 2) * 100) / 100;
    const low = Math.round((Math.min(open, close) - Math.random() * 2) * 100) / 100;
    const volume = Math.round(40_000_000 + Math.random() * 30_000_000);
    data.push({ time: d.toISOString().slice(0, 10), open, high, low, close, volume });
  }
  return data;
}

// --- Quarterly Revenue/NI bar data -------------------------------------------

const QUARTERLY_BAR_DATA = [
  { period: 'Q2 2025', revenue: 81797, ebitda: 27100, fcf: 24100 },
  { period: 'Q3 2025', revenue: 85777, ebitda: 28900, fcf: 24300 },
  { period: 'Q4 2025', revenue: 94930, ebitda: 32500, fcf: 25700 },
  { period: 'Q1 2026', revenue: 119500, ebitda: 43200, fcf: 32000 },
];

function StockCandlestick() {
  const ohlcData = useMemo(() => generateOHLC(), []);
  return <CandlestickChart data={ohlcData} height={300} showVolume />;
}

// --- Component ---------------------------------------------------------------

export default function CompanyOverview() {
  const navigate = useNavigate();
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // Fetch company profile
  const { data: companyData, isLoading: loadingCompany } = useQuery<CompanyInfo>({
    queryKey: ['company', 'profile', resolvedId],
    queryFn: () => api.get(`/v4/entities/${resolvedId}/profile`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const company = companyData ?? MOCK_COMPANY;

  // Fetch KPIs / ratios
  const { data: kpiData, isLoading: loadingKpis } = useQuery<MetricItem[]>({
    queryKey: ['company', 'kpis', resolvedId],
    queryFn: () => api.get(`/v4/entities/${resolvedId}/ratios`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const kpis = kpiData ?? MOCK_METRICS;

  // Fetch quarterly financials
  const { data: quarterlyRaw, isLoading: loadingQuarterly } = useQuery<QuarterlyFinancial[]>({
    queryKey: ['company', 'quarterly', resolvedId],
    queryFn: () => api.get(`/v4/entities/${resolvedId}/financials/quarterly`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const quarterlyData = quarterlyRaw ?? MOCK_QUARTERLY;

  // Fetch quality scores
  const { data: qualityRaw, isLoading: loadingQuality } = useQuery<QualityScoreItem[]>({
    queryKey: ['company', 'quality', resolvedId],
    queryFn: () => api.get(`/v4/entities/${resolvedId}/quality`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const qualityScores = qualityRaw ?? MOCK_QUALITY;

  // Fetch news
  const { data: newsRaw } = useQuery<NewsItem[]>({
    queryKey: ['company', 'news', resolvedId],
    queryFn: () => api.get(`/v4/entities/${resolvedId}/news`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const newsItems = newsRaw ?? MOCK_NEWS;

  // New hooks for Phase 1
  const { data: sentimentHistory } = useSentimentHistory(resolvedId);
  const { data: earningsSurprises } = useEarningsSurprises(resolvedId);
  const { data: technicalSignals } = useTechnicalSignals(resolvedId);
  const { data: compositeScores } = useCompositeScores(resolvedId);

  const isLoading = loadingCompany || loadingKpis || loadingQuarterly || loadingQuality;

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Security Switcher Hint */}
      <div className="terminal-label" style={{ marginBottom: '8px', fontStyle: 'italic', fontSize: 'var(--text-xs)' }}>
        Type <kbd style={{ background: 'var(--color-surface-overlay)', padding: '1px 5px', borderRadius: '2px', fontFamily: 'var(--font-data)' }}>/</kbd> to search for a company
      </div>

      {/* Company Header */}
      {isLoading ? (
        <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Skeleton width="180px" height="24px" />
          <Skeleton width="60px" height="20px" />
          <Skeleton width="100px" height="16px" />
        </div>
      ) : (
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
            {company.name}
          </h1>
          <span className="terminal-data" style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>
            {company.ticker}
          </span>
          <span className="terminal-label">{company.exchange}</span>
          <span className="terminal-label">|</span>
          <span className="terminal-label">{company.sector}</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span className="terminal-hero">
              ${company.price.toFixed(2)}
            </span>
            <span className="terminal-data" style={{ fontSize: 'var(--text-md)', fontWeight: 500, color: signalColor(company.changePct) }}>
              {company.changePct >= 0 ? '+' : ''}{company.changePct.toFixed(2)}%
            </span>
          </div>
        </div>
      )}

      {/* KPI Row — replaced inline metric cards with KeyMetricsGrid */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <KeyMetricsGrid metrics={kpis} />
      </div>

      {/* 2-column body */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Price Chart (OHLC Candlestick) */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Price Chart (6M)</h2>
            <StockCandlestick />
          </div>

          {/* Quarterly Revenue / EBITDA / FCF */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quarterly Revenue / EBITDA / FCF</h2>
            <BarChartComponent
              data={QUARTERLY_BAR_DATA}
              xKey="period"
              bars={[
                { key: 'revenue', color: '#3B82F6', name: 'Revenue ($M)' },
                { key: 'ebitda', color: '#D4A843', name: 'EBITDA ($M)' },
                { key: 'fcf', color: '#2DB87D', name: 'FCF ($M)' },
              ]}
              height={220}
              showLegend
              yAxisFormat={(v: number) => `$${(v / 1000).toFixed(0)}B`}
            />
          </div>

          {/* Financial Summary */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quarterly Financials</h2>
            {loadingQuarterly ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height="28px" />)}
              </div>
            ) : (
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th className="right">Revenue</th>
                    <th className="right">Net Income</th>
                    <th className="right">EPS</th>
                  </tr>
                </thead>
                <tbody>
                  {quarterlyData.map((q) => (
                    <tr key={q.period}>
                      <td style={{ fontWeight: 500 }}>{q.period}</td>
                      <td className="right">{formatM(q.revenue)}</td>
                      <td className="right">{formatM(q.netIncome)}</td>
                      <td className="right">${q.eps.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Quality Scores — replaced inline progress bars with GaugeChart */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quality Scores</h2>
            {loadingQuality ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} style={{ textAlign: 'center' }}>
                    <Skeleton width="80%" height="12px" />
                    <div style={{ marginTop: '6px' }}><Skeleton width="40px" height="24px" /></div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', justifyItems: 'center' }}>
                {qualityScores.map((s) => (
                  <GaugeChart
                    key={s.name}
                    value={s.value}
                    max={s.maxValue}
                    label={s.name}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Score Breakdowns — Piotroski / Altman / Beneish sub-scores */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--panel-gap)' }}>
            <ScoreBreakdown
              title="Piotroski F-Score"
              overallScore={7}
              scores={PIOTROSKI_BREAKDOWN}
            />
            <ScoreBreakdown
              title="Altman Z-Score"
              overallScore={5}
              scores={ALTMAN_BREAKDOWN}
            />
            <ScoreBreakdown
              title="Beneish M-Score"
              overallScore={7}
              scores={BENEISH_BREAKDOWN}
            />
          </div>

          {/* Composite Scores */}
          {compositeScores && (
            <div className="terminal-panel">
              <h2 className="terminal-section-title">Composite Scores</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                {(['quality', 'value', 'growth', 'momentum', 'volatility'] as const).map((key) => {
                  const score = (compositeScores as any)?.[key];
                  return (
                    <div key={key} style={{ textAlign: 'center', padding: '8px', background: 'var(--color-surface-raised)', borderRadius: '4px' }}>
                      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'capitalize', marginBottom: '4px' }}>{key}</div>
                      <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 700, color: (score ?? 50) >= 70 ? 'var(--color-signal-positive)' : (score ?? 50) >= 40 ? 'var(--color-text-primary)' : 'var(--color-signal-negative)' }}>
                        {score ?? '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Earnings Surprises */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Earnings Surprises</h2>
            {(() => {
              const surprises = (earningsSurprises as any[]) ?? [
                { period: 'Q1 2026', epsEstimate: 2.10, epsActual: 2.18, surprise: 3.81, revenueEstimate: 117800, revenueActual: 119500, revSurprise: 1.44 },
                { period: 'Q4 2025', epsEstimate: 1.60, epsActual: 1.64, surprise: 2.50, revenueEstimate: 93200, revenueActual: 94930, revSurprise: 1.86 },
                { period: 'Q3 2025', epsEstimate: 1.43, epsActual: 1.46, surprise: 2.10, revenueEstimate: 84500, revenueActual: 85777, revSurprise: 1.51 },
                { period: 'Q2 2025', epsEstimate: 1.35, epsActual: 1.40, surprise: 3.70, revenueEstimate: 80500, revenueActual: 81797, revSurprise: 1.61 },
              ];
              return (
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th className="right">EPS Est</th>
                      <th className="right">EPS Act</th>
                      <th className="right">Surprise</th>
                    </tr>
                  </thead>
                  <tbody>
                    {surprises.map((s: any) => (
                      <tr key={s.period}>
                        <td style={{ fontWeight: 500 }}>{s.period}</td>
                        <td className="right">${s.epsEstimate?.toFixed(2)}</td>
                        <td className="right" style={{ fontWeight: 600 }}>${s.epsActual?.toFixed(2)}</td>
                        <td className="right" style={{ color: (s.surprise ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 600 }}>
                          {s.surprise != null ? `${s.surprise >= 0 ? '+' : ''}${s.surprise.toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* News Feed */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">News</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {newsItems.map((n) => (
                <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>
                    {n.headline}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '2px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)' }}>{n.source}</span>
                    <span className="terminal-data" style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{n.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Filings */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Recent Filings</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Type', 'Title'].map((h) => (
                    <th
                      key={h}
                      style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: 500,
                        color: 'var(--color-text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        textAlign: 'left',
                        padding: '4px 8px',
                        borderBottom: '1px solid var(--color-surface-border)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MOCK_FILINGS.map((f) => (
                  <tr key={f.id} style={{ height: '32px' }}>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)', whiteSpace: 'nowrap' }}>
                      {f.date}
                    </td>
                    <td style={{ padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '1px 6px',
                          borderRadius: '3px',
                          fontFamily: 'var(--font-data)',
                          fontSize: 'var(--text-xs)',
                          fontWeight: 600,
                          color: FILING_TYPE_COLORS[f.type] ?? 'var(--color-text-secondary)',
                          background: `color-mix(in srgb, ${FILING_TYPE_COLORS[f.type] ?? 'var(--color-text-secondary)'} 15%, transparent)`,
                        }}
                      >
                        {f.type}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {f.title}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: '8px', textAlign: 'right' }}>
              <span
                onClick={() => navigate('/company/filings')}
                style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', cursor: 'pointer' }}
              >
                View All &rarr;
              </span>
            </div>
          </div>

          {/* Entity Sentiment */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Entity Sentiment</h2>
            <SentimentGauge
              value={0.42}
              momentum="IMPROVING"
              label={`${company.ticker} Market Sentiment`}
            />
          </div>

          {/* Sentiment Trend */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Sentiment Trend (30D)</h2>
            {sentimentHistory ? (
              <TimeSeriesChart
                data={sentimentHistory as any[]}
                series={[{ key: 'sentiment', color: '#3B82F6', name: 'Sentiment', type: 'line' }]}
                height={160}
                showGrid
                showTooltip
              />
            ) : (
              <div style={{ height: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
                  Sentiment history available when API is connected
                </span>
              </div>
            )}
          </div>

          {/* Technical Signals */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Technical Signals</h2>
            {(() => {
              const signals = (technicalSignals as any)?.signals ?? [
                { name: 'RSI (14)', value: '58.2', signal: 'Neutral' },
                { name: 'MACD', value: '1.24', signal: 'Bullish' },
                { name: 'SMA 50', value: '$174.30', signal: 'Above' },
                { name: 'SMA 200', value: '$170.15', signal: 'Above' },
                { name: 'Bollinger Bands', value: 'Mid', signal: 'Neutral' },
              ];
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {signals.map((s: any) => (
                    <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>{s.name}</span>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)' }}>{s.value}</span>
                        <span style={{
                          fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 500,
                          color: s.signal === 'Bullish' || s.signal === 'Above' ? 'var(--color-signal-positive)' : s.signal === 'Bearish' || s.signal === 'Below' ? 'var(--color-signal-negative)' : 'var(--color-text-tertiary)',
                        }}>{s.signal}</span>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>

          {/* Top Holders */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Top Holders</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {MOCK_HOLDERS.map((h) => (
                  <tr key={h.name} style={{ height: '30px' }}>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h.name}
                    </td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {h.shares}
                    </td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', padding: '4px 8px', borderBottom: '1px solid var(--color-surface-border)', textAlign: 'right', whiteSpace: 'nowrap', fontWeight: 600 }}>
                      {h.pctOwnership}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: '8px', textAlign: 'right' }}>
              <span
                onClick={() => navigate('/company/ownership')}
                style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', cursor: 'pointer' }}
              >
                View All &rarr;
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
