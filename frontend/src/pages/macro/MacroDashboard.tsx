// ---------------------------------------------------------------------------
// Macro Dashboard — Economic Indicators, GDP, Inflation, Employment
// ---------------------------------------------------------------------------
import { GDPChart, InflationChart, EmploymentChart, MacroIndicatorTable } from '@/components/macro';
import type { GDPDataPoint, InflationDataPoint, NFPDataPoint, UnemploymentDataPoint, MacroIndicator } from '@/components/macro';

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

const headlineKPIs = [
  { label: 'GDP (QoQ SAAR)', value: '2.4%' },
  { label: 'CPI YoY', value: '3.1%' },
  { label: 'Core PCE YoY', value: '2.8%' },
  { label: 'Unemployment', value: '3.8%' },
  { label: 'Fed Funds Rate', value: '5.25-5.50%' },
  { label: 'ISM Mfg', value: '48.2' },
];

// --- GDPChart data -----------------------------------------------------------

const gdpData: GDPDataPoint[] = [
  { country: 'US',      actual: 2.4, forecast: 2.1, prior: 3.2 },
  { country: 'Euro',    actual: 0.8, forecast: 1.0, prior: 0.5 },
  { country: 'China',   actual: 5.2, forecast: 5.0, prior: 4.9 },
  { country: 'Japan',   actual: 1.9, forecast: 1.2, prior: 1.5 },
  { country: 'UK',      actual: 0.5, forecast: 0.8, prior: 0.3 },
  { country: 'India',   actual: 6.8, forecast: 6.5, prior: 7.2 },
];

// --- InflationChart data (monthly, 24 months) --------------------------------

const inflationData: InflationDataPoint[] = [
  { date: '2024-04', headline: 3.4, core: 3.6, pce: 2.7 },
  { date: '2024-05', headline: 3.3, core: 3.4, pce: 2.6 },
  { date: '2024-06', headline: 3.0, core: 3.3, pce: 2.6 },
  { date: '2024-07', headline: 2.9, core: 3.2, pce: 2.5 },
  { date: '2024-08', headline: 2.5, core: 3.2, pce: 2.5 },
  { date: '2024-09', headline: 2.4, core: 3.3, pce: 2.4 },
  { date: '2024-10', headline: 2.6, core: 3.3, pce: 2.5 },
  { date: '2024-11', headline: 2.7, core: 3.3, pce: 2.6 },
  { date: '2024-12', headline: 2.9, core: 3.2, pce: 2.6 },
  { date: '2025-01', headline: 3.0, core: 3.3, pce: 2.6 },
  { date: '2025-02', headline: 2.8, core: 3.1, pce: 2.5 },
  { date: '2025-03', headline: 3.5, core: 3.8, pce: 2.8 },
  { date: '2025-06', headline: 3.2, core: 3.5, pce: 2.7 },
  { date: '2025-09', headline: 3.0, core: 3.4, pce: 2.7 },
  { date: '2025-12', headline: 3.2, core: 3.7, pce: 2.8 },
  { date: '2026-01', headline: 3.0, core: 3.6, pce: 2.7 },
  { date: '2026-02', headline: 2.8, core: 3.5, pce: 2.6 },
  { date: '2026-03', headline: 3.1, core: 3.8, pce: 2.8 },
];

// --- EmploymentChart data ----------------------------------------------------

const nfpData: NFPDataPoint[] = [
  { date: '2025-04', actual: 165, forecast: 180 },
  { date: '2025-05', actual: 272, forecast: 190 },
  { date: '2025-06', actual: 206, forecast: 200 },
  { date: '2025-07', actual: 114, forecast: 175 },
  { date: '2025-08', actual: 142, forecast: 160 },
  { date: '2025-09', actual: 336, forecast: 170 },
  { date: '2025-10', actual: 150, forecast: 180 },
  { date: '2025-11', actual: 199, forecast: 185 },
  { date: '2025-12', actual: 256, forecast: 170 },
  { date: '2026-01', actual: 353, forecast: 185 },
  { date: '2026-02', actual: 229, forecast: 200 },
  { date: '2026-03', actual: 275, forecast: 198 },
];

const unemploymentData: UnemploymentDataPoint[] = [
  { date: '2025-04', rate: 3.9 },
  { date: '2025-05', rate: 4.0 },
  { date: '2025-06', rate: 4.1 },
  { date: '2025-07', rate: 4.3 },
  { date: '2025-08', rate: 4.2 },
  { date: '2025-09', rate: 4.1 },
  { date: '2025-10', rate: 4.1 },
  { date: '2025-11', rate: 3.9 },
  { date: '2025-12', rate: 3.7 },
  { date: '2026-01', rate: 3.7 },
  { date: '2026-02', rate: 3.7 },
  { date: '2026-03', rate: 3.8 },
];

// --- MacroIndicatorTable data ------------------------------------------------

const macroIndicators: MacroIndicator[] = [
  { name: 'GDP (QoQ SAAR)', actual: 2.4, prior: 3.2, forecast: 2.5, surprise: -0.1, releaseDate: '2026-03-27' },
  { name: 'CPI YoY', actual: 3.1, prior: 3.4, forecast: 3.2, surprise: -0.1, releaseDate: '2026-03-12' },
  { name: 'Core PCE YoY', actual: 2.8, prior: 2.8, forecast: 2.8, surprise: 0.0, releaseDate: '2026-03-28' },
  { name: 'NFP (000s)', actual: 275, prior: 229, forecast: 198, surprise: 77, releaseDate: '2026-03-07' },
  { name: 'ISM Manufacturing', actual: 48.2, prior: 49.1, forecast: 49.5, surprise: -1.3, releaseDate: '2026-03-03' },
  { name: 'Retail Sales MoM', actual: 0.6, prior: -0.8, forecast: 0.3, surprise: 0.3, releaseDate: '2026-03-14' },
];

// --- Component ---------------------------------------------------------------

export default function MacroDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Macro Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>US economic indicators &mdash; GDP, inflation, employment, and activity</p>
      </div>

      {/* Headline KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {headlineKPIs.map((k) => (
          <div key={k.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* GDPChart */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>GDP Growth Comparison</h2>
          <GDPChart data={gdpData} height={280} />
        </div>

        {/* InflationChart */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Inflation Trends</h2>
          <InflationChart data={inflationData} target={2.0} height={280} />
        </div>

        {/* EmploymentChart */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Employment Data</h2>
          <EmploymentChart nfpData={nfpData} unemploymentData={unemploymentData} />
        </div>

        {/* MacroIndicatorTable */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Recent Economic Releases</h2>
          <MacroIndicatorTable indicators={macroIndicators} />
        </div>
      </div>
    </div>
  );
}
