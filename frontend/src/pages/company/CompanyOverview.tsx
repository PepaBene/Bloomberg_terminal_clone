// ---------------------------------------------------------------------------
// Company Overview — Main Company Analysis Page
// ---------------------------------------------------------------------------
// React imports (useMemo removed — no longer needed after OHLC mock removal)
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useSecurityStore } from '@/stores/securityContext';
import { OrderBookDepthChart, VolumeProfileChart } from '@/components/charts';
import type { OrderBookLevel, VolumeProfileLevel } from '@/components/charts';
import { useMarketDepth, useVolumeProfile } from '@/api/hooks/useMarketData';
import { KeyMetricsGrid } from '@/components/company/KeyMetricsGrid';
import type { MetricItem } from '@/components/company/KeyMetricsGrid';
import { PriceChartPanel } from '@/components/company/PriceChartPanel';
import { SentimentGauge } from '@/components/intelligence';
import { EmptyState } from '@/components/feedback';
import { useSentimentHistory, useEarningsSurprises, useTechnicalSignals, useCompositeScores, useCorporateActionsUpcoming } from '@/hooks';
import { TimeSeriesChart } from '@/components/charts';

// --- Helpers -----------------------------------------------------------------

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

interface EntityDTO {
  entity_id: string;
  legal_name: string;
  short_name?: string | null;
  gics_sector?: string | null;
  gics_industry?: string | null;
}

interface NewsArticleDTO {
  id: string;
  title: string;
  source_name?: string | null;
  publish_date?: string | null;
}

// No /v1/market-data/* router is mounted on the backend at all (verified —
// no market_data router in src/api/app.py's include_router calls, and no
// depth/volume-profile schema anywhere in src/schemas/). These hooks will
// 404 until that service exists; the panels below show an honest empty
// state rather than a fabricated order book or volume histogram.
interface OrderBookDepthDTO {
  bids?: OrderBookLevel[];
  asks?: OrderBookLevel[];
}
interface VolumeProfileDTO {
  levels?: VolumeProfileLevel[];
}

const DEFAULT_METRICS: MetricItem[] = [
  { label: 'Market Cap',    value: '—' },
  { label: 'P/E (TTM)',     value: '—' },
  { label: 'EV/EBITDA',     value: '—' },
  { label: 'Rev Growth',    value: '—' },
  { label: 'ROE',           value: '—' },
  { label: 'Div Yield',     value: '—' },
];

const DEFAULT_CORP_ACTIONS: { date: string; type: string; description: string; status: string }[] = [];

interface NewsItem {
  id: string;
  headline: string;
  source: string;
  time: string;
}

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

// --- Component ---------------------------------------------------------------

export default function CompanyOverview() {
  const navigate = useNavigate();
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // Company header comes from the real entity record (GET /v1/entities/{id})
  // enriched with the security store (which already carries ticker/exchange/
  // sector from search). The previous /v1/entities/{id}/profile,
  // /ratios, /financials/quarterly and /quality endpoints DO NOT EXIST — they
  // 404'd and fell back to fabricated placeholders (DATA_WIRING_AUDIT §8.2).
  const { data: entityData, isLoading: loadingCompany } = useQuery<EntityDTO>({
    queryKey: ['entity', resolvedId],
    queryFn: () => api.get(`/v1/entities/${resolvedId}`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const company: CompanyInfo = {
    name: entityData?.short_name || entityData?.legal_name || primary?.name || '',
    ticker: primary?.ticker ?? '—',
    exchange: primary?.exchange ?? '',
    sector: entityData?.gics_sector || primary?.gics_sector || '',
    industry: entityData?.gics_industry || primary?.gics_industry || '',
    price: 0,
    changePct: 0,
  };

  // KPIs / quality are keyed by security_id under /v2 analytics and are not
  // wired here — shown as honest "—" placeholders rather than fabricated values.
  const kpis = DEFAULT_METRICS;

  // Fetch entity news (real: GET /v3/news/{entity_id})
  const { data: newsRaw } = useQuery<NewsArticleDTO[]>({
    queryKey: ['company', 'news', resolvedId],
    queryFn: () => api.get(`/v3/news/${resolvedId}`),
    enabled: !!resolvedId,
    retry: 0,
  });
  const newsItems: NewsItem[] = (Array.isArray(newsRaw) ? newsRaw : []).map((n) => ({
    id: String(n.id),
    headline: n.title,
    source: n.source_name ?? '—',
    time: n.publish_date ? new Date(n.publish_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '',
  }));

  const { data: depthData } = useMarketDepth(company.ticker, { enabled: !!company.ticker && company.ticker !== '—' }) as { data: OrderBookDepthDTO | undefined };
  const { data: volumeProfileData } = useVolumeProfile(company.ticker, { enabled: !!company.ticker && company.ticker !== '—' }) as { data: VolumeProfileDTO | undefined };
  const bids = Array.isArray(depthData?.bids) ? depthData.bids : [];
  const asks = Array.isArray(depthData?.asks) ? depthData.asks : [];
  const volumeLevels = Array.isArray(volumeProfileData?.levels) ? volumeProfileData.levels : [];

  // New hooks for Phase 1
  const { data: sentimentHistory } = useSentimentHistory(resolvedId);
  const { data: earningsSurprises } = useEarningsSurprises(resolvedId);
  const { data: technicalSignals } = useTechnicalSignals(resolvedId);
  const { data: compositeScores } = useCompositeScores(resolvedId);
  const { data: corpActions } = useCorporateActionsUpcoming();

  const isLoading = loadingCompany;

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
          {company.exchange && <span className="terminal-label">{company.exchange}</span>}
          {company.sector && <span className="terminal-label">|</span>}
          {company.sector && <span className="terminal-label">{company.sector}</span>}
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
            <PriceChartPanel securityId={resolvedId} height={300} />
          </div>

          {/* Order Book Depth & Volume Profile — no /v1/market-data/* router
              is mounted on the backend (see OrderBookDepthDTO/VolumeProfileDTO
              above), so these render an honest empty state until that service
              exists rather than a fabricated book or histogram. */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)' }}>
            <div className="terminal-panel">
              <h2 className="terminal-section-title">Order Book Depth</h2>
              {bids.length > 0 && asks.length > 0 ? (
                <OrderBookDepthChart bids={bids} asks={asks} />
              ) : (
                <EmptyState
                  icon="📶"
                  title="Order book unavailable"
                  description="Live bid/ask depth is not wired into this view yet."
                />
              )}
            </div>
            <div className="terminal-panel">
              <h2 className="terminal-section-title">Volume Profile</h2>
              {volumeLevels.length > 0 ? (
                <VolumeProfileChart levels={volumeLevels} />
              ) : (
                <EmptyState
                  icon="📊"
                  title="Volume profile unavailable"
                  description="Volume-by-price data is not wired into this view yet."
                />
              )}
            </div>
          </div>

          {/* Quarterly Financials — the /financials/quarterly endpoint does not
              exist; the income-statement series is keyed differently and isn't
              wired here. Honest empty state rather than a fabricated bar chart. */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quarterly Financials</h2>
            <EmptyState
              icon="📊"
              title="Quarterly financials unavailable"
              description="Financial statements for this company are not wired into this view yet."
            />
          </div>

          {/* Quality Scores — the Piotroski/Altman/Beneish sub-score breakdowns
              are keyed by security_id under /v2 analytics and aren't wired here;
              the real, batch-computed composite scores are shown below. Rather
              than render fabricated all-zero gauges/breakdowns, show an honest
              pointer to the composite panel. */}
          {!compositeScores && (
            <div className="terminal-panel">
              <h2 className="terminal-section-title">Quality Scores</h2>
              <EmptyState
                icon="🎯"
                title="Quality scores unavailable"
                description="Batch-computed quality/valuation scores are not available for this security yet."
              />
            </div>
          )}

          {/* Composite Scores */}
          {!!compositeScores && (
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

          {/* Entity Sentiment — derived from the latest real sentiment-history
              point (not a hardcoded value). Hidden when no history exists. */}
          {(() => {
            const hist = (sentimentHistory as { sentiment?: number }[] | undefined) ?? [];
            const latest = hist.length > 0 ? hist[hist.length - 1]?.sentiment : undefined;
            if (latest == null) return null;
            return (
              <div className="terminal-panel">
                <h2 className="terminal-section-title">Entity Sentiment</h2>
                <SentimentGauge value={latest} label={`${company.ticker} Market Sentiment`} />
              </div>
            );
          })()}

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
