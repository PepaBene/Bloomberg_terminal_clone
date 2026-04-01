// ---------------------------------------------------------------------------
// Primer View — Company Primer Display with Sections
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useCompanyPrimer, useRecentPrimers } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const company = { name: 'Apple Inc.', ticker: 'AAPL', dataCompleteness: 94 };

const sections = [
  { title: 'Business Overview', content: 'Apple designs, manufactures, and sells smartphones, personal computers, tablets, wearables, and accessories. The company also operates a growing services ecosystem including the App Store, Apple Music, iCloud, Apple TV+, and Apple Pay. Revenue is diversified across hardware and services with a growing shift toward recurring services revenue.' },
  { title: 'Competitive Position', content: 'Apple maintains a dominant position through vertical integration, ecosystem lock-in, and premium brand perception. Key moats include the integrated hardware-software ecosystem, developer platform, and ASP premium over Android peers. Services revenue provides an annuity-like stream with 71% gross margins.' },
  { title: 'Key Risks', content: 'Revenue concentration in iPhone (52% of total), China geopolitical risk (18% of revenue), antitrust pressure on App Store commissions, and potential saturation in mature smartphone markets. Hardware replacement cycles extending to 4+ years.' },
  { title: 'Financial Summary', content: 'FY2025 revenue $391B (+2% YoY), net income $101B, FCF $107B. Net leverage 0.4x EBITDA. Capital return program returned $105B in FY2025 through buybacks and dividends. ROE 156.8% (elevated by negative book value periods).' },
];

const dataQuality = [
  { field: 'Financials (10 years)', completeness: 100 },
  { field: 'SEC Filings', completeness: 100 },
  { field: 'Ownership Data', completeness: 98 },
  { field: 'Credit Ratings', completeness: 95 },
  { field: 'ESG Scores', completeness: 82 },
  { field: 'Management Bios', completeness: 88 },
];

export default function PrimerView() {
  const { entityId } = useParams<{ entityId: string }>();
  const resolvedId = entityId ?? 'AAPL';
  const { data: apiPrimer } = useCompanyPrimer(resolvedId) as { data: any };
  const { data: apiRecent } = useRecentPrimers() as { data: any };
  const [refreshing, setRefreshing] = useState(false);

  const primerData = (apiPrimer as any) ?? { company, sections, dataQuality };
  const activeSections = primerData.sections ?? sections;
  const activeQuality = primerData.dataQuality ?? dataQuality;
  const activeCompany = primerData.company ?? company;

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await api.post(RESEARCH.primers.refresh(resolvedId), {}); } catch {}
    setRefreshing(false);
  };
  const handleDownload = async () => {
    try { await api.get(RESEARCH.primers.download(resolvedId)); } catch {}
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Company Primer</h1>
        <span style={{ ...dataStyle, color: 'var(--color-accent-primary)', fontWeight: 600 }}>{activeCompany.ticker}</span>
        <span style={labelStyle}>{activeCompany.name}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)' }}>Data Completeness: {activeCompany.dataCompleteness}%</span>
        <button className="btn-ghost" onClick={handleDownload} style={{ marginLeft: '8px' }}>Download PDF</button>
        <button className="btn-primary" onClick={handleRefresh} disabled={refreshing} style={{ marginLeft: '4px' }}>
          {refreshing ? 'Refreshing…' : 'Refresh Primer'}
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
      </div>
    </div>
  );
}
