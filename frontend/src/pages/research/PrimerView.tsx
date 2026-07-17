// ---------------------------------------------------------------------------
// Primer View — Company Primer Display with Sections
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useCompanyPrimer, useRecentPrimers } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
import type { CompanyPrimer } from '@/types/research';

interface PrimerSection {
  title: string;
  content: string;
}

// CompanyPrimerResponse's section fields are dicts (business_model,
// competitive_landscape, financial_health, strategic_initiatives,
// risk_factors, recent_catalysts, analyst_consensus), not plain prose --
// render them as readable "key: value" text rather than [object Object].
function formatPrimerValue(value: unknown): string {
  if (value == null || value === '') return '';
  if (Array.isArray(value)) {
    return value.map(formatPrimerValue).filter(Boolean).join('; ');
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, val]) => {
        const formatted = formatPrimerValue(val);
        return formatted ? `${key}: ${formatted}` : '';
      })
      .filter(Boolean)
      .join(' • ');
  }
  return String(value);
}

function buildPrimerSections(primer: CompanyPrimer): PrimerSection[] {
  const sections: PrimerSection[] = [];
  if (primer.executive_summary) {
    sections.push({ title: 'Executive Summary', content: primer.executive_summary });
  }
  const dictSections: Array<[string, unknown]> = [
    ['Business Model', primer.business_model],
    ['Competitive Landscape', primer.competitive_landscape],
    ['Financial Health', primer.financial_health],
    ['Strategic Initiatives', primer.strategic_initiatives],
    ['Risk Factors', primer.risk_factors],
    ['Recent Catalysts', primer.recent_catalysts],
    ['Analyst Consensus', primer.analyst_consensus],
  ];
  for (const [title, value] of dictSections) {
    const content = formatPrimerValue(value);
    if (content) sections.push({ title, content });
  }
  return sections;
}
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

function SkeletonBlock({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: '4px',
      }}
    />
  );
}

export default function PrimerView() {
  const { entityId } = useParams<{ entityId: string }>();
  // Don't fall back to AAPL — that silently shows Apple's primer for any
  // missing entity ID. Just disable the queries until a real ID is present.
  const resolvedId = entityId;
  const { data: apiPrimer, isLoading, isError } = useCompanyPrimer(resolvedId);
  const { data: apiRecent, isLoading: recentLoading } = useRecentPrimers();
  const [refreshing, setRefreshing] = useState(false);

  const primerData = apiPrimer;
  const activeSections = primerData ? buildPrimerSections(primerData) : [];
  // CompanyPrimerResponse only carries a single overall
  // data_completeness_score -- there's no per-field completeness breakdown
  // to show a multi-row list for.
  const activeQuality =
    primerData?.data_completeness_score != null
      ? [{ field: 'Overall Data Completeness', completeness: primerData.data_completeness_score }]
      : undefined;

  const recentPrimers = apiRecent ?? [];

  const handleRefresh = async () => {
    if (!resolvedId) return;
    setRefreshing(true);
    try {
      await api.post(RESEARCH.primers.refresh(resolvedId), {});
    } catch (err) {
      console.error('Primer refresh failed:', err);
    }
    setRefreshing(false);
  };
  const handleDownload = async () => {
    if (!resolvedId) return;
    try {
      await api.get(RESEARCH.primers.download(resolvedId));
    } catch (err) {
      console.error('Primer download failed:', err);
    }
  };

  // Empty state: no entityId provided
  if (!resolvedId) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
        </div>
        <div style={{ ...panelStyle, textAlign: 'center', padding: '48px' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '12px' }}>
            No entity selected
          </div>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: 0 }}>
            Select a security or navigate from a company page to view the primer.
          </p>
        </div>
        {/* Recent Primers Sidebar */}
        {recentPrimers.length > 0 && (
          <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
            <h2 style={sectionTitle}>Recent Primers</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {recentPrimers.map((p) => (
                <div key={p.entity_id} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', cursor: 'pointer', padding: '4px 0' }}>
                  {p.entity_id} &mdash; v{p.primer_version}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
          <SkeletonBlock width="60px" height="20px" />
          <SkeletonBlock width="140px" height="16px" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} style={panelStyle}>
                <SkeletonBlock width="160px" height="20px" />
                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <SkeletonBlock width="100%" height="14px" />
                  <SkeletonBlock width="95%" height="14px" />
                  <SkeletonBlock width="85%" height="14px" />
                </div>
              </div>
            ))}
          </div>
          <div style={panelStyle}>
            <SkeletonBlock width="120px" height="20px" />
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonBlock key={i} width="100%" height="24px" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
        </div>
        <div style={{ ...panelStyle, borderLeft: '3px solid var(--color-signal-negative)' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>Failed to load primer data for {resolvedId}. Please try again later.</span>
        </div>
      </div>
    );
  }

  // No primer data
  if (!primerData || activeSections.length === 0) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
          <span style={{ ...dataStyle, color: 'var(--color-accent-primary)', fontWeight: 600 }}>{resolvedId}</span>
          <button className="btn-primary" onClick={handleRefresh} disabled={refreshing} style={{ marginLeft: 'auto' }}>
            {refreshing ? 'Generating...' : 'Generate Primer'}
          </button>
        </div>
        <div style={{ ...panelStyle, textAlign: 'center', padding: '48px' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
            No primer available for {resolvedId}
          </div>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: 0 }}>
            Click "Generate Primer" to create one.
          </p>
        </div>
      </div>
    );
  }

  // Main primer view
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
        {/* CompanyPrimerResponse has no ticker/company-name field -- resolvedId
            (the entity UUID from the route) is the only identifier available here. */}
        <span style={{ ...dataStyle, color: 'var(--color-accent-primary)', fontWeight: 600 }}>{resolvedId}</span>
        {primerData.data_completeness_score != null && (
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)' }}>Data Completeness: {primerData.data_completeness_score}%</span>
        )}
        <button className="btn-ghost" onClick={handleDownload} style={{ marginLeft: primerData.data_completeness_score != null ? '8px' : 'auto' }}>Download PDF</button>
        <button className="btn-primary" onClick={handleRefresh} disabled={refreshing} style={{ marginLeft: '4px' }}>
          {refreshing ? 'Refreshing...' : 'Refresh Primer'}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          {activeSections.map((s) => (
            <div key={s.title} style={panelStyle}>
              <h2 style={sectionTitle}>{s.title}</h2>
              <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.6, margin: 0 }}>{s.content}</p>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          {/* Data Quality */}
          {activeQuality && activeQuality.length > 0 && (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Data Quality</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {activeQuality.map((d) => (
                  <div key={d.field}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                      <span style={labelStyle}>{d.field}</span>
                      <span style={{ ...dataStyle, fontSize: 'var(--text-sm)' }}>{d.completeness}%</span>
                    </div>
                    <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                      <div style={{ height: '100%', width: `${d.completeness}%`, background: d.completeness >= 95 ? 'var(--color-signal-positive)' : d.completeness >= 80 ? 'var(--color-signal-warning)' : 'var(--color-signal-negative)', borderRadius: '2px' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Recent Primers */}
          {recentLoading ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Recent Primers</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonBlock key={i} width="100%" height="16px" />
                ))}
              </div>
            </div>
          ) : recentPrimers.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Recent Primers</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {recentPrimers.map((p) => (
                  <div key={p.entity_id} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', cursor: 'pointer', padding: '4px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                    {p.entity_id} &mdash; v{p.primer_version}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
