// ---------------------------------------------------------------------------
// Country Risk Dashboard
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { CountryRiskRanking, GeopoliticalEventCard } from '@/components/global';
import type { CountryRisk as CountryRiskType, GeopoliticalEvent } from '@/components/global';

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

// --- Mock Data ---------------------------------------------------------------

interface CountryRiskRow {
  rank: number;
  country: string;
  code: string;
  compositeScore: number;
  political: number;
  economic: number;
  sanctions: number;
  classification: string;
  trend: string;
}

const countries: CountryRiskRow[] = [
  { rank: 1,  country: 'Switzerland',    code: 'CH', compositeScore: 12, political: 8,  economic: 10, sanctions: 0,  classification: 'LOW',      trend: 'Stable' },
  { rank: 2,  country: 'Singapore',      code: 'SG', compositeScore: 18, political: 14, economic: 12, sanctions: 0,  classification: 'LOW',      trend: 'Stable' },
  { rank: 3,  country: 'Norway',         code: 'NO', compositeScore: 15, political: 10, economic: 14, sanctions: 0,  classification: 'LOW',      trend: 'Stable' },
  { rank: 4,  country: 'Germany',        code: 'DE', compositeScore: 25, political: 22, economic: 28, sanctions: 0,  classification: 'MODERATE', trend: 'Deteriorating' },
  { rank: 5,  country: 'United States',  code: 'US', compositeScore: 28, political: 32, economic: 22, sanctions: 2,  classification: 'MODERATE', trend: 'Stable' },
  { rank: 6,  country: 'Japan',          code: 'JP', compositeScore: 24, political: 18, economic: 30, sanctions: 0,  classification: 'MODERATE', trend: 'Stable' },
  { rank: 7,  country: 'India',          code: 'IN', compositeScore: 42, political: 38, economic: 44, sanctions: 5,  classification: 'MODERATE', trend: 'Improving' },
  { rank: 8,  country: 'South Africa',   code: 'ZA', compositeScore: 48, political: 52, economic: 46, sanctions: 3,  classification: 'ELEVATED', trend: 'Deteriorating' },
  { rank: 9,  country: 'Brazil',         code: 'BR', compositeScore: 52, political: 56, economic: 48, sanctions: 2,  classification: 'ELEVATED', trend: 'Improving' },
  { rank: 10, country: 'Mexico',         code: 'MX', compositeScore: 54, political: 58, economic: 50, sanctions: 4,  classification: 'ELEVATED', trend: 'Stable' },
  { rank: 11, country: 'Egypt',          code: 'EG', compositeScore: 62, political: 65, economic: 60, sanctions: 8,  classification: 'HIGH',     trend: 'Deteriorating' },
  { rank: 12, country: 'Turkey',         code: 'TR', compositeScore: 67, political: 72, economic: 64, sanctions: 12, classification: 'HIGH',     trend: 'Deteriorating' },
  { rank: 13, country: 'Pakistan',       code: 'PK', compositeScore: 74, political: 78, economic: 72, sanctions: 14, classification: 'HIGH',     trend: 'Stable' },
  { rank: 14, country: 'Russia',         code: 'RU', compositeScore: 89, political: 85, economic: 82, sanctions: 95, classification: 'EXTREME',  trend: 'Deteriorating' },
  { rank: 15, country: 'Venezuela',      code: 'VE', compositeScore: 92, political: 94, economic: 96, sanctions: 88, classification: 'EXTREME',  trend: 'Stable' },
];

interface GeoEvent {
  id: number;
  title: string;
  region: string;
  severity: 'Critical' | 'High' | 'Medium';
  date: string;
}

const geoEvents: GeoEvent[] = [
  { id: 1, title: 'EU imposes new sanctions package on Russian energy sector',        region: 'Europe',       severity: 'Critical', date: '2026-03-25' },
  { id: 2, title: 'Turkey central bank emergency rate hike amid lira volatility',     region: 'Middle East',  severity: 'High',     date: '2026-03-24' },
  { id: 3, title: 'Brazil constitutional reform vote approaching deadline',            region: 'LatAm',        severity: 'Medium',   date: '2026-03-23' },
  { id: 4, title: 'South China Sea military exercises escalate tensions',              region: 'Asia-Pacific', severity: 'High',     date: '2026-03-22' },
  { id: 5, title: 'Venezuela opposition protests intensify ahead of referendum',       region: 'LatAm',        severity: 'High',     date: '2026-03-21' },
];

// --- KPI data ----------------------------------------------------------------
const kpis = [
  { label: 'Countries Tracked', value: '195' },
  { label: 'High Risk',         value: '23',  color: 'var(--color-signal-negative)' },
  { label: 'Elevated',          value: '34',  color: 'var(--color-quality-2)' },
  { label: 'Active Events',     value: '12',  color: 'var(--color-accent-primary)' },
];

// --- CountryRiskRanking component data ----------------------------------------

const countryRiskData: CountryRiskType[] = countries.map((c) => ({
  code: c.code,
  name: c.country,
  composite: c.compositeScore,
  political: c.political,
  economic: c.economic,
  sanctions: c.sanctions,
  classification: c.classification,
  trend: c.trend,
  history: [c.compositeScore - 4, c.compositeScore - 2, c.compositeScore - 1, c.compositeScore, c.compositeScore + 1],
}));

// --- GeopoliticalEvent component data ----------------------------------------

const geoEventCards: GeopoliticalEvent[] = geoEvents.map((ev) => ({
  title: ev.title,
  description: `${ev.severity} severity event in ${ev.region}`,
  severity: ev.severity,
  countries: [ev.region],
  startDate: ev.date,
  status: 'Active',
}));

// --- Component ---------------------------------------------------------------

export default function CountryRisk() {
  const [_refresh] = useState(0);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Country Risk
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Country risk scores, political/economic/sanctions assessment, and geopolitical events
        </p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {kpis.map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, padding: '12px 16px' }}>
            <div style={labelStyle}>{kpi.label}</div>
            <div style={{ ...dataStyle, fontSize: 'var(--text-xl)', fontWeight: 700, marginTop: '4px', color: kpi.color || 'var(--color-text-primary)' }}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* CountryRiskRanking Component replaces inline table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Rankings</h2>
          <CountryRiskRanking countries={countryRiskData} />
        </div>

        {/* GeopoliticalEventCard Components replace inline events */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Geopolitical Events</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {geoEventCards.map((ev, idx) => (
              <GeopoliticalEventCard key={idx} event={ev} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
