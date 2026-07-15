// ---------------------------------------------------------------------------
// Company Overview — Main Company Analysis Page
// ---------------------------------------------------------------------------
// React imports (useMemo removed — no longer needed after OHLC mock removal)
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useSecurityStore } from '@/stores/securityContext';
import { CandlestickChart, BarChartComponent, GaugeChart, ScoreBreakdown } from '@/components/charts';
import type { CandlestickDataPoint, ScoreItem } from '@/components/charts';
import { KeyMetricsGrid } from '@/components/company/KeyMetricsGrid';
import type { MetricItem } from '@/components/company/KeyMetricsGrid';
import { SentimentGauge } from '@/components/intelligence';
import { useSentimentHistory, useEarningsSurprises, useTechnicalSignals, useCompositeScores, useCorporateActionsUpcoming } from '@/hooks';
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

const DEFAULT_COMPANY: CompanyInfo = {
  name: '',
  ticker: '—',
  exchange: '',
  sector: '',
  industry: '',
  price: 0,
  changePct: 0,
};

const DEFAULT_METRICS: MetricItem[] = [
  { label: 'Market Cap',    value: '—' },
  { label: 'P/E (TTM)',     value: '—' },
  { label: 'EV/EBITDA',     value: '—' },
  { label: 'Rev Growth',    value: '—' },
  { label: 'ROE',           value: '—' },
  { label: 'Div Yield',     value: '—' },
];

interface QuarterlyFinancial {
  period: string;
  revenue: number;
  netIncome: number;
  ebitda: number;
  fcf: number;
  eps: number;
}

const DEFAULT_QUARTERLY: QuarterlyFinancial[] = [];

interface QualityScoreItem {
  name: string;
  value: number;
  maxValue: number;
  classification: string;
}

const DEFAULT_QUALITY: QualityScoreItem[] = [
  { name: 'Piotroski F-Score', value: 0, maxValue: 9, classification: '—' },
  { name: 'Altman Z-Score',    value: 0, maxValue: 10, classification: '—' },
  { name: 'Composite Quality', value: 0, maxValue: 100, classification: '—' },
];

// Piotroski sub-score breakdown
const PIOTROSKI_BREAKDOWN: ScoreItem[] = [
  { name: 'Positive Net Income', score: 0, max: 1 },
  { name: 'Positive Operating CF', score: 0, max: 1 },
  { name: 'ROA Increasing', score: 0, max: 1 },
  { name: 'CF > Net Income', score: 0, max: 1 },
  { name: 'Lower Leverage', score: 0, max: 1 },
  { name: 'Higher Current Ratio', score: 0, max: 1 },
  { name: 'No Dilution', score: 0, max: 1 },
  { name: 'Higher Gross Margin', score: 0, max: 1 },
  { name: 'Higher Asset Turnover', score: 0, max: 1 },
];

const ALTMAN_BREAKDOWN: ScoreItem[] = [
  { name: 'Working Capital / Assets', score: 0, max: 1, description: '—' },
  { name: 'Retained Earnings / Assets', score: 0, max: 1, description: '—' },
  { name: 'EBIT / Assets', score: 0, max: 1, description: '—' },
  { name: 'Mkt Cap / Total Liabilities', score: 0, max: 1, description: '—' },
  { name: 'Revenue / Assets', score: 0, max: 1, description: '—' },
];

const DEFAULT_CORP_ACTIONS: { date: string; type: string; description: string; status: string }[] = [];

const BENEISH_BREAKDOWN: ScoreItem[] = [
  { name: 'Days Sales in Receivables', score: 0, max: 1, description: '—' },
  { name: 'Gross Margin Index', score: 0, max: 1, description: '—' },
  { name: 'Asset Quality Index', score: 0, max: 1, description: '—' },
  { name: 'Sales Growth Index', score: 0, max: 1, description: '—' },
  { name: 'Depreciation Index', score: 0, max: 1, description: '—' },
  { name: 'SGA Index', score: 0, max: 1, description: '—' },
  { name: 'Leverage Index', score: 0, max: 1, description: '—' },
  { name: 'Total Accruals', score: 0, max: 1, description: '—' },
];

interface NewsItem {
  id: string;
  headline: string;
  source: string;
  time: string;
}

const DEFAULT_NEWS: NewsItem[] = [];

interface FilingItem {
  id: string;
  date: string;
  type: '10-K' | '10-Q' | '8-K';
  title: string;
}

const DEFAULT_FILINGS: FilingItem[] = [];

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

const DEFAULT_HOLDERS: HolderItem[] = [];

// --- OHLC default (empty until API provides real data) ----------------------

const DEFAULT_OHLC: CandlestickDataPoint[] = [];

// --- Quarterly Revenue/NI bar data -------------------------------------------

const DEFAULT_QUARTERLY_BAR_DATA: { period: string; revenue: number; ebitda: number; fcf: number }[] = [];

function StockCandlestick() {
  return <CandlestickChart data={DEFAULT_OHLC} height={300} showVolume />;
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
    queryFn: () => api.get(`/v1/entities/${resolvedId}/profile`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const company = companyData ?? DEFAULT_COMPANY;

  // Fetch KPIs / ratios
  const { data: kpiData, isLoading: loadingKpis } = useQuery<MetricItem[]>({
    queryKey: ['company', 'kpis', resolvedId],
    queryFn: () => api.get(`/v1/entities/${resolvedId}/ratios`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const kpis = kpiData ?? DEFAULT_METRICS;

  // Fetch quarterly financials
  const { data: quarterlyRaw, isLoading: loadingQuarterly } = useQuery<QuarterlyFinancial[]>({
    queryKey: ['company', 'quarterly', resolvedId],
    queryFn: () => api.get(`/v1/entities/${resolvedId}/financials/quarterly`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const quarterlyData = quarterlyRaw ?? DEFAULT_QUARTERLY;

  // Fetch quality scores
  const { data: qualityRaw, isLoading: loadingQuality } = useQuery<QualityScoreItem[]>({
    queryKey: ['company', 'quality', resolvedId],
    queryFn: () => api.get(`/v1/entities/${resolvedId}/quality`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const qualityScores = qualityRaw ?? DEFAULT_QUALITY;

  // Fetch news
  const { data: newsRaw } = useQuery<NewsItem[]>({
    queryKey: ['company', 'news', resolvedId],
    queryFn: () => api.get(`/v1/entities/${resolvedId}/news`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const newsItems = newsRaw ?? DEFAULT_NEWS;

  // New hooks for Phase 1
  const { data: sentimentHistory } = useSentimentHistory(resolvedId);
  const { data: earningsSurprises } = useEarningsSurprises(resolvedId);
  const { data: technicalSignals } = useTechnicalSignals(resolvedId);
  const { data: compositeScores } = useCompositeScores(resolvedId);
  const { data: corpActions } = useCorporateActionsUpcoming();

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
              data={DEFAULT_QUARTERLY_BAR_DATA}
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
              overallScore={0}
              scores={PIOTROSKI_BREAKDOWN}
            />
            <ScoreBreakdown
              title="Altman Z-Score"
              overallScore={0}
              scores={ALTMAN_BREAKDOWN}
            />
            <ScoreBreakdown
              title="Beneish M-Score"
              overallScore={0}
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
              const surprises = (earningsSurprises as any[]) ?? [];
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

          {/* Corporate Actions Timeline */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Corporate Actions</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {((corpActions as any[]) ?? DEFAULT_CORP_ACTIONS).map((a: any, i: number) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', minWidth: '80px' }}>{a.date}</span>
                  <span style={{
                    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, padding: '1px 6px', borderRadius: '2px',
                    color: a.type === 'Earnings' ? 'var(--color-accent-primary)' : a.type === 'Dividend' ? 'var(--color-signal-positive)' : 'var(--color-text-secondary)',
                    background: a.type === 'Earnings' ? 'color-mix(in srgb, var(--color-accent-primary) 15%, transparent)' : a.type === 'Dividend' ? 'color-mix(in srgb, var(--color-signal-positive) 15%, transparent)' : 'var(--color-surface-overlay)',
                  }}>{a.type}</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', flex: 1 }}>{a.description}</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: a.status === 'Active' ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)' }}>{a.status}</span>
                </div>
              ))}
            </div>
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
                {DEFAULT_FILINGS.map((f) => (
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
              const signals = (technicalSignals as any)?.signals ?? [];
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
                {DEFAULT_HOLDERS.map((h) => (
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

          {/* Pillar 4 — additional analysis tools */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">More Analysis</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {[
                { label: 'Complex Structure', description: 'Subsidiary tree, share classes, debt waterfall', path: '/company/complex-structure' },
                { label: 'Smart Money', description: 'Notable 13F managers, insiders, politicians', path: '/smart-money' },
                { label: 'Model Builder', description: 'Auto-scored economic/market/company models', path: '/research/model-builder' },
              ].map((tool) => (
                <div
                  key={tool.path}
                  onClick={() => navigate(tool.path)}
                  style={{ display: 'flex', flexDirection: 'column', padding: '6px 8px', borderRadius: '4px', cursor: 'pointer', borderBottom: '1px solid var(--color-surface-border)' }}
                  onMouseOver={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)'; }}
                  onMouseOut={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                >
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{tool.label}</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{tool.description}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
