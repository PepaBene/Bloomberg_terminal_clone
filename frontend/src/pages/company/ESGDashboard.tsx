// ---------------------------------------------------------------------------
// ESG Dashboard — Environmental, Social, Governance Scores & Analysis
// ---------------------------------------------------------------------------
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useESG, useESGScores, useESGHistory } from '@/hooks';
import { GaugeChart } from '@/components/charts';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// Mock fallback data
const MOCK_ESG = {
  overall: 72, environmental: 68, social: 75, governance: 82,
  rating: 'AA', ratingAgency: 'MSCI', lastUpdated: '2026-02-15',
};

const MOCK_METRICS = [
  { category: 'Environmental', metrics: [
    { name: 'Carbon Emissions (Scope 1+2)', value: '22.4M tCO2e', trend: 'improving' },
    { name: 'Renewable Energy %', value: '100%', trend: 'stable' },
    { name: 'Water Intensity', value: '0.12 m³/unit', trend: 'improving' },
    { name: 'Waste Diverted from Landfill', value: '92%', trend: 'improving' },
  ]},
  { category: 'Social', metrics: [
    { name: 'Employee Satisfaction', value: '4.2/5.0', trend: 'stable' },
    { name: 'Gender Diversity (Mgmt)', value: '35%', trend: 'improving' },
    { name: 'Lost-Time Injury Rate', value: '0.22', trend: 'improving' },
    { name: 'Supply Chain Audits', value: '1,100+', trend: 'stable' },
  ]},
  { category: 'Governance', metrics: [
    { name: 'Board Independence', value: '87.5%', trend: 'stable' },
    { name: 'Board Gender Diversity', value: '37.5%', trend: 'improving' },
    { name: 'CEO/Chair Separation', value: 'Yes', trend: 'stable' },
    { name: 'Say-on-Pay Approval', value: '94.2%', trend: 'stable' },
  ]},
];

const MOCK_CONTROVERSIES = [
  { date: '2026-01-15', severity: 'Medium', topic: 'Supply Chain Labor', description: 'Allegations of excessive overtime at key supplier facility in Southeast Asia.' },
  { date: '2025-09-22', severity: 'Low', topic: 'E-Waste Management', description: 'NGO report questions recycling rate claims for older product models.' },
];

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

  const { data: apiESG } = useESG(resolvedId);
  const { data: apiScores } = useESGScores(resolvedId);
  const { data: apiHistory } = useESGHistory(resolvedId);

  const esg = (apiESG as any) ?? MOCK_ESG;
  const metrics = (apiScores as any)?.categories ?? MOCK_METRICS;
  const controversies = (apiESG as any)?.controversies ?? MOCK_CONTROVERSIES;

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          ESG Dashboard
        </h1>
        <p style={labelStyle}>Environmental, Social & Governance Analysis</p>
      </div>

      {/* Score Gauges */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        <div style={{ ...panelStyle, textAlign: 'center' }}>
          <GaugeChart value={esg.overall} max={100} label="Overall ESG" />
          <div style={{ marginTop: '8px' }}>
            <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-accent-primary)' }}>{esg.rating}</span>
            <span style={{ ...labelStyle, marginLeft: '6px' }}>{esg.ratingAgency}</span>
          </div>
        </div>
        {[{ key: 'environmental', label: 'Environmental' }, { key: 'social', label: 'Social' }, { key: 'governance', label: 'Governance' }].map((pillar) => (
          <div key={pillar.key} style={{ ...panelStyle, textAlign: 'center' }}>
            <GaugeChart value={esg[pillar.key]} max={100} label={pillar.label} />
          </div>
        ))}
      </div>

      {/* ESG Metrics by Category */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {metrics.map((cat: any) => (
          <div key={cat.category} style={panelStyle}>
            <h2 style={sectionTitle}>{cat.category}</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {cat.metrics.map((m: any) => (
                <div key={m.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span style={labelStyle}>{m.name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600 }}>{m.value}</span>
                    <span style={{ fontSize: 'var(--text-xs)', color: trendColor(m.trend) }}>{trendIcon(m.trend)}</span>
                  </div>
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
            {controversies.map((c: any, i: number) => (
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
