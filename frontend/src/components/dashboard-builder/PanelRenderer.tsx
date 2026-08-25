// ---------------------------------------------------------------------------
// Dashboard-builder panel content — dispatches each PANEL_TYPES entry
// (see PanelCatalog.tsx) to a real, data-backed widget instead of the raw
// componentType string PanelSlot used to print as filler text.
//
// Every panel below fetches through the same real hooks the rest of the app
// uses and falls back to an honest EmptyState — never fabricated rows —
// matching the "honesty pass" convention established across RiskPage,
// SectorView, GlobalDashboard and CompanyOverview.
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import { useSecurityStore } from '@/stores/securityContext';
import { EmptyState } from '@/components/feedback';
import { WatchlistPanel } from '@/components/watchlist/WatchlistPanel';
import { IndustryTreemap } from '@/components/sector';
import { PriceChartPanel } from '@/components/company/PriceChartPanel';
import { MacroIndicatorTable } from '@/components/macro';
import type { MacroIndicator } from '@/components/macro';
import { KeySpreadsPanel } from '@/components/fi';
import type { SpreadRow } from '@/components/fi';
import { AlertInbox } from '@/components/alerts';
import type { Alert as InboxAlert } from '@/components/alerts';
import {
  useEntity,
  useAnalyticsRatios,
  useTechnicalSignals,
  useMacroIndicators,
  useCreditSpreads,
  useAlerts,
  usePortfolios,
  usePortfolioVaR,
  usePortfolioPositions,
} from '@/hooks';
import { usePrebuiltScreens } from '@/api/hooks/useScreening';
import { useLatestNews } from '@/api/hooks/useNews';
import { useTodayBriefing } from '@/api/hooks/useResearch';
import { api } from '@/api/client';
import { ALERTS } from '@/api/endpoints';

const emptyBox: CSSProperties = { padding: '4px 0' };
const rowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '5px 0',
  borderBottom: '1px solid var(--color-surface-border)',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
};
const labelText: CSSProperties = { color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' };
const valueText: CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-primary)', flexShrink: 0, marginLeft: 8 };

/** Resolves the "current" security for symbol-scoped panels the same way CompanyOverview.tsx does. */
function useCurrentSecurityId(): string | undefined {
  const primary = useSecurityStore((s) => s.primary);
  return primary?.entity_id ?? primary?.security_id;
}

/* ------------------------------------------------------------------ */
/*  Market Data panels                                                 */
/* ------------------------------------------------------------------ */

function CompanyOverviewPanel() {
  const primary = useSecurityStore((s) => s.primary);
  const { data: entity } = useEntity(primary?.entity_id ?? '', { enabled: !!primary?.entity_id }) as {
    data: { legal_name?: string; short_name?: string; gics_sector?: string; gics_industry?: string } | undefined;
  };

  if (!primary) {
    return <EmptyState icon="🏢" title="No security selected" description="Search for a company to populate this panel." />;
  }

  return (
    <div style={emptyBox}>
      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
        {entity?.short_name || entity?.legal_name || primary.name}
      </div>
      <div style={{ fontFamily: 'var(--font-data)', color: 'var(--color-accent-primary)', fontWeight: 600, marginTop: 2 }}>
        {primary.ticker} {primary.exchange && <span style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)' }}>· {primary.exchange}</span>}
      </div>
      {(entity?.gics_sector || primary.gics_sector) && (
        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: 6 }}>
          {entity?.gics_sector ?? primary.gics_sector} {(entity?.gics_industry ?? primary.gics_industry) && `· ${entity?.gics_industry ?? primary.gics_industry}`}
        </div>
      )}
    </div>
  );
}

function PriceChartPanelWidget() {
  const securityId = useCurrentSecurityId();
  if (!securityId) {
    return <EmptyState icon="📈" title="No security selected" description="Search for a company to load its price chart." />;
  }
  return <PriceChartPanel securityId={securityId} height={220} />;
}

interface RatiosByCategory {
  [category: string]: Record<string, number | null>;
}

function FundamentalsPanel() {
  const securityId = useCurrentSecurityId();
  const { data } = useAnalyticsRatios(securityId) as { data: RatiosByCategory | undefined };

  const rows = useMemo(() => {
    if (!data) return [];
    const out: { label: string; value: number }[] = [];
    for (const [category, metrics] of Object.entries(data)) {
      for (const [name, value] of Object.entries(metrics ?? {})) {
        if (value != null) out.push({ label: `${category} · ${name}`, value });
      }
    }
    return out.slice(0, 8);
  }, [data]);

  if (!securityId) return <EmptyState icon="📊" title="No security selected" description="Search for a company to load its ratios." />;
  if (rows.length === 0) return <EmptyState icon="📊" title="No ratio data available" description="Fundamentals have not been computed for this security yet." />;

  return (
    <div style={emptyBox}>
      {rows.map((r) => (
        <div key={r.label} style={rowStyle}>
          <span style={{ ...labelText, textTransform: 'capitalize' }}>{r.label.replace(/_/g, ' ')}</span>
          <span style={valueText}>{r.value.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

interface PrebuiltScreen {
  id?: string;
  name?: string;
  description?: string;
}

function ScreenerPanelWidget() {
  const { data } = usePrebuiltScreens() as { data: PrebuiltScreen[] | { screens?: PrebuiltScreen[] } | undefined };
  const screens = Array.isArray(data) ? data : Array.isArray((data as { screens?: PrebuiltScreen[] })?.screens) ? (data as { screens: PrebuiltScreen[] }).screens : [];

  if (screens.length === 0) {
    return <EmptyState icon="🔍" title="No prebuilt screens available" description="No saved screens have been created for this deployment yet." />;
  }

  return (
    <div style={emptyBox}>
      {screens.slice(0, 8).map((s, i) => (
        <div key={s.id ?? i} style={rowStyle}>
          <span style={labelText}>{s.name ?? 'Untitled screen'}</span>
        </div>
      ))}
    </div>
  );
}

function WatchlistPanelWidget() {
  return <WatchlistPanel />;
}

function SectorHeatmapPanel() {
  return <IndustryTreemap height={220} showMetricPicker={false} />;
}

/* ------------------------------------------------------------------ */
/*  Analytics panels                                                   */
/* ------------------------------------------------------------------ */

interface PortfolioListItem {
  id: string;
  portfolio_name: string;
}

function useFirstPortfolio() {
  const { data } = usePortfolios() as { data: PortfolioListItem[] | undefined };
  return Array.isArray(data) && data.length > 0 ? data[0] : undefined;
}

function RiskPanelWidget() {
  const portfolio = useFirstPortfolio();
  const { data: varData } = usePortfolioVaR(portfolio?.id) as {
    data: { var_1d_95: number | null; var_1d_99: number | null; var_10d_95: number | null } | null | undefined;
  };

  if (!portfolio) return <EmptyState icon="⚠️" title="No portfolios found" description="Create a portfolio to see risk metrics here." />;
  if (!varData) return <EmptyState icon="⏳" title="Loading risk metrics…" />;

  const stats = [
    { label: '1D VaR (95%)', value: varData.var_1d_95 },
    { label: '1D VaR (99%)', value: varData.var_1d_99 },
    { label: '10D VaR (95%)', value: varData.var_10d_95 },
  ];

  return (
    <div style={emptyBox}>
      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginBottom: 6 }}>{portfolio.portfolio_name}</div>
      {stats.map((s) => (
        <div key={s.label} style={rowStyle}>
          <span style={labelText}>{s.label}</span>
          <span style={valueText}>{s.value != null ? `$${(s.value / 1000).toFixed(0)}K` : '—'}</span>
        </div>
      ))}
    </div>
  );
}

interface TechnicalSignal {
  indicator: string;
  name: string;
  value: number;
  signal: string | null;
}

function QuantPanelWidget() {
  const securityId = useCurrentSecurityId();
  const { data } = useTechnicalSignals(securityId) as { data: { signals?: TechnicalSignal[] } | undefined };
  const signals = Array.isArray(data?.signals) ? data!.signals! : [];

  if (!securityId) return <EmptyState icon="🧮" title="No security selected" description="Search for a company to load technical signals." />;
  if (signals.length === 0) return <EmptyState icon="🧮" title="No signals available" description="Not enough price history to compute technical signals." />;

  return (
    <div style={emptyBox}>
      {signals.slice(0, 8).map((s) => (
        <div key={s.indicator} style={rowStyle}>
          <span style={labelText}>{s.name}</span>
          <span style={valueText}>
            {s.value.toFixed(2)}
            {s.signal && <span style={{ marginLeft: 6, color: 'var(--color-text-tertiary)' }}>{s.signal}</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

function MacroPanelWidget() {
  const { data } = useMacroIndicators() as { data: { indicators?: MacroIndicator[] } | undefined };
  const indicators = Array.isArray(data?.indicators) ? data!.indicators! : [];

  if (indicators.length === 0) return <EmptyState icon="🌐" title="No macro data available" description="No economic indicators have been ingested yet." />;
  return <MacroIndicatorTable indicators={indicators.slice(0, 8)} />;
}

function FIDashboardPanelWidget() {
  const { data } = useCreditSpreads() as { data: { spreads?: SpreadRow[] } | undefined };
  const spreads = Array.isArray(data?.spreads) ? data!.spreads! : [];

  if (spreads.length === 0) return <EmptyState icon="📉" title="No spread data available" description="Credit spread data has not been ingested for this deployment yet." />;
  return <KeySpreadsPanel spreads={spreads.slice(0, 8)} />;
}

/* ------------------------------------------------------------------ */
/*  Intelligence panels                                                */
/* ------------------------------------------------------------------ */

interface NewsArticle {
  id?: string | number;
  title?: string;
  source_name?: string;
  publish_date?: string;
}

function NewsPanelWidget() {
  const { data } = useLatestNews() as { data: NewsArticle[] | undefined };
  const articles = Array.isArray(data) ? data : [];

  if (articles.length === 0) return <EmptyState icon="📰" title="No news available" description="No recent articles have been ingested yet." />;

  return (
    <div style={emptyBox}>
      {articles.slice(0, 6).map((a, i) => (
        <div key={a.id ?? i} style={rowStyle}>
          <span style={labelText}>{a.title ?? 'Untitled'}</span>
          <span style={{ ...valueText, fontFamily: 'var(--font-ui)', color: 'var(--color-text-tertiary)' }}>{a.source_name ?? ''}</span>
        </div>
      ))}
    </div>
  );
}

function AlertsPanelWidget() {
  const { data } = useAlerts() as {
    data: { id: string; alert_type: string; priority: string; title: string; is_acknowledged: boolean; created_at: string }[] | undefined;
  };
  const rows = Array.isArray(data) ? data : [];

  const alerts: InboxAlert[] = rows.map((a) => ({
    id: String(a.id),
    title: a.title,
    description: a.alert_type.replace(/_/g, ' ').toLowerCase(),
    severity: (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes((a.priority ?? '').toUpperCase())
      ? (a.priority.toUpperCase() as InboxAlert['severity'])
      : 'MEDIUM'),
    createdAt: a.created_at,
    isRead: a.is_acknowledged === true,
  }));

  if (alerts.length === 0) return <EmptyState icon="🔔" title="No active alerts" description="No alerts have fired for this deployment yet." />;

  return (
    <AlertInbox
      alerts={alerts.slice(0, 6)}
      onAcknowledge={(id) => { api.post(ALERTS.acknowledge(id), {}).catch(() => {}); }}
      onDismiss={() => {}}
    />
  );
}

interface BriefingResponse {
  id?: string;
  title?: string;
  summary?: string;
  market_sentiment?: string;
  highlights?: string[];
}

function ResearchPanelWidget() {
  const { data } = useTodayBriefing() as { data: BriefingResponse | undefined };

  if (!data || !data.summary) {
    return <EmptyState icon="📋" title="No briefing available" description="Today's research briefing has not been generated yet." />;
  }

  return (
    <div style={emptyBox}>
      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 6 }}>
        {data.title ?? "Today's Briefing"}
      </div>
      <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5, margin: 0 }}>
        {data.summary}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Portfolio panel                                                    */
/* ------------------------------------------------------------------ */

interface PositionRow {
  ticker?: string;
  security_ticker?: string;
  weight?: number;
  weight_pct?: number;
  market_value?: number;
}

function PortfolioPanelWidget() {
  const portfolio = useFirstPortfolio();
  const { data } = usePortfolioPositions(portfolio?.id) as { data: PositionRow[] | { positions?: PositionRow[] } | undefined };
  const positions = Array.isArray(data) ? data : Array.isArray((data as { positions?: PositionRow[] })?.positions) ? (data as { positions: PositionRow[] }).positions : [];

  if (!portfolio) return <EmptyState icon="💼" title="No portfolios found" description="Create a portfolio to see holdings here." />;
  if (positions.length === 0) return <EmptyState icon="💼" title="No positions" description={`${portfolio.portfolio_name} has no open positions.`} />;

  return (
    <div style={emptyBox}>
      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginBottom: 6 }}>{portfolio.portfolio_name}</div>
      {positions.slice(0, 8).map((p, i) => (
        <div key={p.ticker ?? p.security_ticker ?? i} style={rowStyle}>
          <span style={labelText}>{p.ticker ?? p.security_ticker ?? '—'}</span>
          <span style={valueText}>{(p.weight ?? p.weight_pct) != null ? `${((p.weight ?? p.weight_pct)!).toFixed(1)}%` : '—'}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Dispatch                                                           */
/* ------------------------------------------------------------------ */

const PANEL_COMPONENTS: Record<string, () => React.ReactElement> = {
  CompanyOverview: CompanyOverviewPanel,
  PriceChart: PriceChartPanelWidget,
  Fundamentals: FundamentalsPanel,
  Screener: ScreenerPanelWidget,
  Watchlist: WatchlistPanelWidget,
  SectorHeatmap: SectorHeatmapPanel,
  Risk: RiskPanelWidget,
  Quant: QuantPanelWidget,
  Macro: MacroPanelWidget,
  FIDashboard: FIDashboardPanelWidget,
  News: NewsPanelWidget,
  Alerts: AlertsPanelWidget,
  Research: ResearchPanelWidget,
  Portfolio: PortfolioPanelWidget,
};

export interface PanelRendererProps {
  componentType: string;
}

/** Renders the real widget for a dashboard-builder panel's componentType, or an honest fallback for an unknown type. */
export function PanelRenderer({ componentType }: PanelRendererProps) {
  const Component = PANEL_COMPONENTS[componentType];
  if (!Component) {
    return <EmptyState icon="❓" title="Unknown panel type" description={`"${componentType}" is not a recognized panel type.`} />;
  }
  return <Component />;
}

export default PanelRenderer;
