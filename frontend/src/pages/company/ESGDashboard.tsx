// ---------------------------------------------------------------------------
// ESG Dashboard — Environmental, Social, Governance Scores & Analysis
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useESG } from '@/hooks';
import { GaugeChart } from '@/components/charts';

// --- API response shapes (subset of backend schemas actually read) ---------
// Mirrors `ESGOverviewResponse`/`ESGScoreResponse`/`ESGMetricResponse`/
// `ESGControversyResponse` (src/schemas/esg.py) — `GET /v1/entities/{id}/esg`
// bundles all three collections in one call; `scores` is ordered most-recent
// first.
interface ESGScoreApi {
  provider: string;
  as_of_date: string;
  esg_score: number | null;
  esg_rating: string | null;
  environmental_score: number | null;
  social_score: number | null;
  governance_score: number | null;
  score_trend: string | null;
}
interface ESGMetricApi {
  metric_type: string;
  metric_category: string | null;
  value: number | null;
  unit: string | null;
}
interface ESGControversyApi {
  controversy_type: string;
  severity: string | null;
  description: string | null;
  start_date: string | null;
}
interface ESGOverviewApi {
  scores?: ESGScoreApi[];
  metrics?: ESGMetricApi[];
  controversies?: ESGControversyApi[];
}

interface ESGMetricCategoryGroup {
  category: string;
  metrics: { name: string; value: string }[];
}

interface ControversyRow {
  topic: string;
  date: string;
  description: string;
  severity: string;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// Default empty data (populated by API)
const MOCK_ESG = {
  overall: 0, environmental: 0, social: 0, governance: 0,
  rating: '—', ratingAgency: '—', lastUpdated: '', trend: null as string | null,
};

const MOCK_METRICS: ESGMetricCategoryGroup[] = [];

const MOCK_CONTROVERSIES: ControversyRow[] = [];

function trendIcon(trend: string): string {
  if (trend === 'improving') return '▲';
  if (trend === 'deteriorating') return '▼';
  return '●';
}

function trendColor(trend: string): string {
  if (trend === 'improving') return 'var(--color-signal-positive)';
  if (trend === 'deteriorating') return 'var(--color-signal-negative)';
  return 'var(--color-text-tertiary)';
}

export default function ESGDashboard() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const { data: apiESG } = useESG(resolvedId) as { data: ESGOverviewApi | undefined };

  // [P1-FP-014 fix] `ESGOverviewResponse` bundles `scores` (most-recent
  // first), `metrics`, and `controversies` in one `/esg` call — read the
  // real fields instead of the previously-assumed (and wrong-path)
  // `apiScores?.categories` / `apiESG?.controversies` shape.
  const latestScore = apiESG?.scores?.[0];
  const esg = latestScore
    ? {
        overall: latestScore.esg_score ?? 0,
        environmental: latestScore.environmental_score ?? 0,
        social: latestScore.social_score ?? 0,
        governance: latestScore.governance_score ?? 0,
        rating: latestScore.esg_rating ?? '—',
        ratingAgency: latestScore.provider ?? '—',
        lastUpdated: latestScore.as_of_date ?? '',
        trend: latestScore.score_trend,
      }
    : MOCK_ESG;

  // `ESGMetricResponse` has no per-metric trend field, so the trend arrow
  // that used to be rendered per-row (from a nonexistent `m.trend`) has been
  // dropped rather than fabricated — group the real flat metric list by
  // `metric_category` instead.
  const metrics: ESGMetricCategoryGroup[] = useMemo(() => {
    const rows = apiESG?.metrics;
    if (!Array.isArray(rows) || rows.length === 0) return MOCK_METRICS;
    const byCategory = new Map<string, { name: string; value: string }[]>();
    for (const m of rows) {
      const category = m.metric_category ?? 'Other';
      const list = byCategory.get(category) ?? [];
      list.push({ name: m.metric_type, value: m.value != null ? `${m.value}${m.unit ? ` ${m.unit}` : ''}` : '—' });
      byCategory.set(category, list);
    }
    return Array.from(byCategory.entries()).map(([category, catMetrics]) => ({ category, metrics: catMetrics }));
  }, [apiESG]);

  const controversies: ControversyRow[] = useMemo(() => {
    const rows = apiESG?.controversies;
    if (!Array.isArray(rows) || rows.length === 0) return MOCK_CONTROVERSIES;
    return rows.map((c) => ({
      topic: c.controversy_type,
      date: c.start_date ?? '',
      description: c.description ?? '',
      severity: c.severity ?? '',
    }));
  }, [apiESG]);

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          ESG Dashboard
        </h1>
        <p style={labelStyle}>Environmental, Social & Governance Analysis</p>
      </div>

      {/* Score Gauges */}
      {!latestScore && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
          <p style={labelStyle}>No ESG score is available for this entity.</p>
        </div>
      )}
      {latestScore && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        <div style={{ ...panelStyle, textAlign: 'center' }}>
          <GaugeChart value={esg.overall} max={100} label="Overall ESG" />
          <div style={{ marginTop: '8px' }}>
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-accent-primary)' }}>{esg.rating}</span>
            <span style={{ ...labelStyle, marginLeft: '6px' }}>{esg.ratingAgency}</span>
            {esg.trend && (
              <span style={{ fontSize: 'var(--text-xs)', color: trendColor(esg.trend), marginLeft: '6px' }}>
                {trendIcon(esg.trend)} {esg.trend}
              </span>
            )}
          </div>
        </div>
        {[
          { key: 'environmental', label: 'Environmental', value: esg.environmental },
          { key: 'social', label: 'Social', value: esg.social },
          { key: 'governance', label: 'Governance', value: esg.governance },
        ].map((pillar) => (
          <div key={pillar.key} style={{ ...panelStyle, textAlign: 'center' }}>
            <GaugeChart value={pillar.value} max={100} label={pillar.label} />
          </div>
        ))}
      </div>}

      {/* ESG Metrics by Category */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {metrics.map((cat) => (
          <div key={cat.category} style={panelStyle}>
            <h2 style={sectionTitle}>{cat.category}</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {cat.metrics.map((m) => (
                <div key={m.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span style={labelStyle}>{m.name}</span>
                  <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600 }}>{m.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Controversies */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>ESG Controversies</h2>
        {controversies.length === 0 ? (
          <p style={labelStyle}>No active controversies</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {controversies.map((c, i: number) => (
              <div key={i} style={{ padding: '10px', background: 'var(--color-surface-raised)', borderRadius: '4px', borderLeft: `3px solid ${c.severity === 'High' ? 'var(--color-signal-negative)' : c.severity === 'Medium' ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{c.topic}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{c.date}</span>
                </div>
                <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', margin: 0, lineHeight: 1.5 }}>{c.description}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
