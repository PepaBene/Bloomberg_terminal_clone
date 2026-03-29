// ---------------------------------------------------------------------------
// Ownership Dashboard — Institutional Holders, Insider Ownership, Short Interest
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { OwnershipSummary } from '@/components/company/OwnershipSummary';
import type { Holder } from '@/components/company/OwnershipSummary';
import { OwnershipChangeTable, ShortInterestChart, ActivistBanner } from '@/components/ownership';
import type { OwnershipChange, ShortInterestDataPoint, ActivistInfo } from '@/components/ownership';

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

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

// OwnershipSummary component data
const topHolders: Holder[] = [
  { name: 'Vanguard Group', shares: 1310000000, pctOwned: 8.51, change: 12400000, value: 234100000000 },
  { name: 'BlackRock Inc.', shares: 1010000000, pctOwned: 6.56, change: -8200000, value: 180500000000 },
  { name: 'Berkshire Hathaway', shares: 905000000, pctOwned: 5.88, change: 0, value: 161700000000 },
  { name: 'State Street Corp', shares: 622000000, pctOwned: 4.04, change: 3100000, value: 111200000000 },
  { name: 'FMR LLC (Fidelity)', shares: 358000000, pctOwned: 2.33, change: -15600000, value: 64000000000 },
  { name: 'Geode Capital Mgmt', shares: 312000000, pctOwned: 2.03, change: 5800000, value: 55800000000 },
  { name: 'Northern Trust', shares: 198000000, pctOwned: 1.29, change: -2100000, value: 35400000000 },
  { name: 'T. Rowe Price', shares: 175000000, pctOwned: 1.14, change: 8900000, value: 31300000000 },
];

const ownershipSummary = [
  { label: 'Institutional', value: '60.8%' },
  { label: 'Insider', value: '0.07%' },
  { label: 'Retail / Other', value: '39.13%' },
  { label: 'Shares Outstanding', value: '15.41B' },
  { label: 'Float', value: '15.40B' },
  { label: '# Institutions', value: '5,842' },
];

// --- OwnershipChangeTable data (8 holders with quarterly changes) ------------

const ownershipChanges: OwnershipChange[] = [
  { holder: 'Vanguard Group', priorShares: 1297600000, currentShares: 1310000000, change: 12400000, changePct: 0.96, filingDate: '2026-03-15' },
  { holder: 'BlackRock Inc.', priorShares: 1018200000, currentShares: 1010000000, change: -8200000, changePct: -0.81, filingDate: '2026-03-14' },
  { holder: 'Berkshire Hathaway', priorShares: 905000000, currentShares: 905000000, change: 0, changePct: 0, filingDate: '2026-03-12' },
  { holder: 'State Street Corp', priorShares: 618900000, currentShares: 622000000, change: 3100000, changePct: 0.50, filingDate: '2026-03-14' },
  { holder: 'FMR LLC (Fidelity)', priorShares: 373600000, currentShares: 358000000, change: -15600000, changePct: -4.18, filingDate: '2026-03-13' },
  { holder: 'Geode Capital Mgmt', priorShares: 306200000, currentShares: 312000000, change: 5800000, changePct: 1.89, filingDate: '2026-03-15' },
  { holder: 'Northern Trust', priorShares: 200100000, currentShares: 198000000, change: -2100000, changePct: -1.05, filingDate: '2026-03-14' },
  { holder: 'T. Rowe Price', priorShares: 166100000, currentShares: 175000000, change: 8900000, changePct: 5.36, filingDate: '2026-03-12' },
];

// --- ShortInterestChart data (12 months) -------------------------------------

const shortInterestHistory: ShortInterestDataPoint[] = [
  { date: '2025-04-15', shortInterest: 145000000, daysToCover: 1.6, shortPctFloat: 0.94 },
  { date: '2025-05-15', shortInterest: 138000000, daysToCover: 1.5, shortPctFloat: 0.90 },
  { date: '2025-06-15', shortInterest: 130000000, daysToCover: 1.4, shortPctFloat: 0.85 },
  { date: '2025-07-15', shortInterest: 142000000, daysToCover: 1.5, shortPctFloat: 0.92 },
  { date: '2025-08-15', shortInterest: 155000000, daysToCover: 1.7, shortPctFloat: 1.01 },
  { date: '2025-09-15', shortInterest: 148000000, daysToCover: 1.6, shortPctFloat: 0.96 },
  { date: '2025-10-15', shortInterest: 135000000, daysToCover: 1.4, shortPctFloat: 0.88 },
  { date: '2025-11-15', shortInterest: 128000000, daysToCover: 1.3, shortPctFloat: 0.83 },
  { date: '2025-12-15', shortInterest: 132000000, daysToCover: 1.4, shortPctFloat: 0.86 },
  { date: '2026-01-15', shortInterest: 125000000, daysToCover: 1.4, shortPctFloat: 0.82 },
  { date: '2026-02-15', shortInterest: 119000000, daysToCover: 1.3, shortPctFloat: 0.78 },
  { date: '2026-03-15', shortInterest: 112000000, daysToCover: 1.2, shortPctFloat: 0.73 },
];

// --- ActivistBanner data -----------------------------------------------------

const activistInfo: ActivistInfo = {
  name: 'Elliott Management',
  position: 'New Position',
  filingDate: '2026-03-10',
  stake: 4.2,
  intent: 'Seeking board representation and capital return acceleration',
};

// --- Component ---------------------------------------------------------------

export default function OwnershipDashboard() {
  const [showBanner, setShowBanner] = useState(true);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Activist Banner at top */}
      {showBanner && (
        <div style={{ marginBottom: 'var(--panel-gap)' }}>
          <ActivistBanner activist={activistInfo} onDismiss={() => setShowBanner(false)} />
        </div>
      )}

      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Ownership Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      {/* Summary Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {ownershipSummary.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* OwnershipSummary Component */}
        <OwnershipSummary
          holders={topHolders}
          insiderPct={0.07}
          institutionalPct={60.8}
        />

        {/* ShortInterestChart Component */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Short Interest (12M)</h2>
          <ShortInterestChart data={shortInterestHistory} />
        </div>
      </div>

      {/* OwnershipChangeTable below */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Quarterly Ownership Changes</h2>
        <OwnershipChangeTable changes={ownershipChanges} />
      </div>
    </div>
  );
}
