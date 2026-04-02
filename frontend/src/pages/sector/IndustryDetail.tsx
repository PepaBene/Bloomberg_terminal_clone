// ---------------------------------------------------------------------------
// Industry Detail — Economics, Cycle Position, Competitive Structure
// ---------------------------------------------------------------------------

import { useParams } from 'react-router-dom';
import { useIndustryOverview, useIndustryEconomics, useIndustryCycle } from '@/hooks';

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

function signalColor(v: number): string {
  return v >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const industry = {
  name: 'Semiconductors & Semiconductor Equipment',
  sector: 'Information Technology',
  cyclePosition: 'Expansion',
  hhi: 1842,
};

const economics = [
  { metric: 'TAM (2026E)', value: '$612B' },
  { metric: '5Y Revenue CAGR', value: '12.4%' },
  { metric: 'Avg Gross Margin', value: '52.8%' },
  { metric: 'Avg ROIC', value: '18.5%' },
  { metric: 'CapEx Intensity', value: '22.1%' },
  { metric: 'R&D Intensity', value: '18.7%' },
];

const topCompanies = [
  { ticker: 'NVDA', name: 'NVIDIA', mktCap: '$2.18T', pe: 62.5, revGrowth: 122.4, margin: 72.8 },
  { ticker: 'TSM', name: 'TSMC', mktCap: '$780B', pe: 24.2, revGrowth: 28.5, margin: 55.2 },
  { ticker: 'AVGO', name: 'Broadcom', mktCap: '$620B', pe: 35.8, revGrowth: 44.2, margin: 68.5 },
  { ticker: 'AMD', name: 'AMD', mktCap: '$285B', pe: 45.2, revGrowth: 18.8, margin: 48.2 },
  { ticker: 'INTC', name: 'Intel', mktCap: '$132B', pe: 28.5, revGrowth: -2.5, margin: 41.5 },
  { ticker: 'QCOM', name: 'Qualcomm', mktCap: '$198B', pe: 18.2, revGrowth: 8.2, margin: 56.8 },
];

const competitiveMetrics = [
  { factor: 'Market Concentration (HHI)', value: '1,842', assessment: 'Moderately Concentrated' },
  { factor: 'Barriers to Entry', value: 'Very High', assessment: 'Capital & IP intensive' },
  { factor: 'Supplier Power', value: 'Moderate', assessment: 'Equipment oligopoly' },
  { factor: 'Buyer Power', value: 'Low', assessment: 'High switching costs' },
  { factor: 'Threat of Substitutes', value: 'Low', assessment: 'No viable alternatives' },
];

// --- Component ---------------------------------------------------------------

export default function IndustryDetail() {
  const { gicsCode } = useParams<{ gicsCode: string }>();
  const { data: apiOverview } = useIndustryOverview(gicsCode) as { data: any };
  const { data: apiEconomics } = useIndustryEconomics(gicsCode) as { data: any };
  const { data: apiCycle } = useIndustryCycle(gicsCode) as { data: any };

  const activeIndustry = (apiOverview as any)?.industry ?? industry;
  const activeEconomics = (apiEconomics as any)?.economics ?? economics;
  const activeTopCompanies = (apiOverview as any)?.topCompanies ?? topCompanies;
  const activeCompetitiveMetrics = (apiOverview as any)?.competitiveMetrics ?? competitiveMetrics;
  const activeCyclePosition = (apiCycle as any)?.cyclePosition ?? activeIndustry.cyclePosition;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {activeIndustry.name}
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{activeIndustry.sector} &mdash; Cycle: <span style={{ color: 'var(--color-signal-positive)', fontWeight: 500 }}>{activeCyclePosition}</span></p>
      </div>

      {/* Economics KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeEconomics.map((e) => (
          <div key={e.metric} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{e.metric}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{e.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Top Companies */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Top Companies</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Ticker', 'Company', 'Mkt Cap', 'P/E', 'Rev Growth', 'Gross Margin'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: ['Ticker', 'Company'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeTopCompanies.map((c) => (
                <tr key={c.ticker} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{c.ticker}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.mktCap}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.pe.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(c.revGrowth) }}>{c.revGrowth >= 0 ? '+' : ''}{c.revGrowth.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.margin.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Competitive Structure */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Competitive Structure</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {activeCompetitiveMetrics.map((m) => (
                <tr key={m.factor} style={{ height: 'var(--table-row-height)', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{m.factor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{m.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '8px' }}>
            {activeCompetitiveMetrics.map((m) => (
              <div key={m.factor} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                {m.factor}: {m.assessment}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
