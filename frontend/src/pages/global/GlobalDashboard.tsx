// ---------------------------------------------------------------------------
// Global Intelligence Dashboard
// ---------------------------------------------------------------------------
import { BarChartComponent } from '@/components/charts';

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

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function riskColor(classification: string): string {
  switch (classification) {
    case 'Low':       return 'var(--color-quality-5)';
    case 'Moderate':  return 'var(--color-quality-3)';
    case 'Elevated':  return 'var(--color-quality-2)';
    case 'High':      return 'var(--color-signal-negative)';
    default:          return 'var(--color-text-secondary)';
  }
}

// --- Mock Data ---------------------------------------------------------------

interface CountryRisk {
  rank: number;
  country: string;
  code: string;
  compositeScore: number;
  classification: string;
  trend: string;
  political: number;
  economic: number;
}

const countryRisks: CountryRisk[] = [
  { rank: 1,  country: 'Switzerland',    code: 'CH', compositeScore: 92, classification: 'Low',      trend: 'Stable',      political: 95, economic: 90 },
  { rank: 2,  country: 'Norway',         code: 'NO', compositeScore: 90, classification: 'Low',      trend: 'Stable',      political: 92, economic: 88 },
  { rank: 3,  country: 'Singapore',      code: 'SG', compositeScore: 89, classification: 'Low',      trend: 'Improving',   political: 88, economic: 91 },
  { rank: 4,  country: 'United States',  code: 'US', compositeScore: 82, classification: 'Low',      trend: 'Stable',      political: 78, economic: 86 },
  { rank: 5,  country: 'Germany',        code: 'DE', compositeScore: 80, classification: 'Low',      trend: 'Deteriorating', political: 82, economic: 78 },
  { rank: 6,  country: 'Japan',          code: 'JP', compositeScore: 78, classification: 'Moderate', trend: 'Stable',      political: 80, economic: 75 },
  { rank: 7,  country: 'China',          code: 'CN', compositeScore: 58, classification: 'Moderate', trend: 'Deteriorating', political: 52, economic: 64 },
  { rank: 8,  country: 'Brazil',         code: 'BR', compositeScore: 48, classification: 'Elevated', trend: 'Improving',   political: 42, economic: 54 },
  { rank: 9,  country: 'India',          code: 'IN', compositeScore: 55, classification: 'Moderate', trend: 'Improving',   political: 50, economic: 60 },
  { rank: 10, country: 'Turkey',         code: 'TR', compositeScore: 38, classification: 'High',     trend: 'Deteriorating', political: 35, economic: 42 },
];

interface Commodity {
  name: string;
  code: string;
  price: number;
  unit: string;
  change1d: number;
  changeYtd: number;
}

const commodities: Commodity[] = [
  { name: 'Gold',        code: 'XAU', price: 2182.40, unit: '$/oz',  change1d: 0.42,  changeYtd: 7.28 },
  { name: 'Crude Oil',   code: 'CL',  price: 81.24,   unit: '$/bbl', change1d: -0.68, changeYtd: 12.34 },
  { name: 'Copper',      code: 'HG',  price: 4.12,    unit: '$/lb',  change1d: 1.24,  changeYtd: 5.82 },
  { name: 'Natural Gas', code: 'NG',  price: 1.78,    unit: '$/MMBtu', change1d: -2.18, changeYtd: -28.42 },
];

interface CentralBankRate {
  bank: string;
  code: string;
  rate: number;
  stance: string;
  nextMeeting: string;
}

const centralBanks: CentralBankRate[] = [
  { bank: 'Federal Reserve',      code: 'FED', rate: 5.375, stance: 'Restrictive', nextMeeting: '2026-05-07' },
  { bank: 'European Central Bank', code: 'ECB', rate: 4.000, stance: 'Restrictive', nextMeeting: '2026-04-17' },
  { bank: 'Bank of Japan',        code: 'BOJ', rate: 0.250, stance: 'Accommodative', nextMeeting: '2026-04-25' },
  { bank: 'Bank of England',      code: 'BOE', rate: 5.250, stance: 'Restrictive', nextMeeting: '2026-05-09' },
];

function stanceColor(stance: string): string {
  switch (stance) {
    case 'Restrictive':    return 'var(--color-signal-negative)';
    case 'Neutral':        return 'var(--color-signal-neutral)';
    case 'Accommodative':  return 'var(--color-signal-positive)';
    default:               return 'var(--color-text-secondary)';
  }
}

function trendIcon(trend: string): string {
  switch (trend) {
    case 'Improving':     return '\u2191';
    case 'Deteriorating': return '\u2193';
    default:              return '\u2192';
  }
}

function trendColor(trend: string): string {
  switch (trend) {
    case 'Improving':     return 'var(--color-signal-positive)';
    case 'Deteriorating': return 'var(--color-signal-negative)';
    default:              return 'var(--color-signal-neutral)';
  }
}

// --- GDP Growth Mock Data ----------------------------------------------------

const GDP_DATA = [
  { country: 'India',   gdp2024: 6.8, gdp2025: 6.5 },
  { country: 'China',   gdp2024: 5.2, gdp2025: 4.6 },
  { country: 'US',      gdp2024: 2.5, gdp2025: 2.1 },
  { country: 'Japan',   gdp2024: 1.9, gdp2025: 1.0 },
  { country: 'EU',      gdp2024: 0.8, gdp2025: 1.2 },
  { country: 'Brazil',  gdp2024: 2.9, gdp2025: 1.8 },
  { country: 'UK',      gdp2024: 0.5, gdp2025: 1.1 },
  { country: 'Germany', gdp2024: -0.1, gdp2025: 0.8 },
];

// --- Component ---------------------------------------------------------------

export default function GlobalDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Global Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Country risk, commodities, and central bank policy monitoring
        </p>
      </div>

      {/* GDP Growth Comparison */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>GDP Growth Comparison (%)</h2>
        <BarChartComponent
          data={GDP_DATA}
          xKey="country"
          bars={[
            { key: 'gdp2024', color: '#3B82F6', name: '2024 (Actual)' },
            { key: 'gdp2025', color: '#2DB87D', name: '2025 (Forecast)' },
          ]}
          height={260}
          showLegend
          yAxisFormat={(v: number) => `${v.toFixed(1)}%`}
        />
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Country Risk Rankings */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Country Risk Rankings</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['#', 'Country', 'Score', 'Risk', 'Trend', 'Political', 'Economic'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Country' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {countryRisks.map((c) => (
                  <tr key={c.code} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-tertiary)' }}>{c.rank}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-tertiary)', marginRight: '6px' }}>{c.code}</span>
                      {c.country}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{c.compositeScore}</td>
                    <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '1px 6px', borderRadius: '2px', color: riskColor(c.classification), background: `color-mix(in srgb, ${riskColor(c.classification)} 15%, transparent)` }}>
                        {c.classification}
                      </span>
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: trendColor(c.trend) }}>
                      {trendIcon(c.trend)} {c.trend}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.political}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.economic}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Commodity Prices */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Commodities</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {commodities.map((c) => (
                <div key={c.code} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div>
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{c.name}</span>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginLeft: '6px' }}>{c.code}</span>
                    </div>
                    <span style={{ ...dataStyle, fontWeight: 600 }}>{c.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{c.unit}</span>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: signalColor(c.change1d) }}>
                        1D: {c.change1d >= 0 ? '+' : ''}{c.change1d.toFixed(2)}%
                      </span>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: signalColor(c.changeYtd) }}>
                        YTD: {c.changeYtd >= 0 ? '+' : ''}{c.changeYtd.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Central Bank Rates */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Central Bank Rates</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {centralBanks.map((cb) => (
                <div key={cb.code} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div>
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{cb.bank}</span>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginLeft: '6px' }}>{cb.code}</span>
                    </div>
                    <span style={{ ...dataStyle, fontWeight: 600 }}>{cb.rate.toFixed(3)}%</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: stanceColor(cb.stance),
                      background: `color-mix(in srgb, ${stanceColor(cb.stance)} 15%, transparent)`,
                    }}>
                      {cb.stance}
                    </span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
                      Next: {cb.nextMeeting}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
