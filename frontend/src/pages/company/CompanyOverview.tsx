// ---------------------------------------------------------------------------
// Company Overview — Main Company Analysis Page
// ---------------------------------------------------------------------------

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

function qualityColor(score: number): string {
  if (score >= 8) return 'var(--color-quality-5)';
  if (score >= 6) return 'var(--color-quality-4)';
  if (score >= 4) return 'var(--color-quality-3)';
  if (score >= 2) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

// --- Mock Data ---------------------------------------------------------------

const company = {
  name: 'Apple Inc.',
  ticker: 'AAPL',
  exchange: 'NASDAQ',
  sector: 'Information Technology',
  industry: 'Technology Hardware, Storage & Peripherals',
  price: 178.72,
  changePct: -0.34,
};

interface KPI {
  label: string;
  value: string;
  subValue?: string;
}

const kpis: KPI[] = [
  { label: 'Market Cap',    value: '$2.78T' },
  { label: 'P/E (TTM)',     value: '28.6x' },
  { label: 'EV/EBITDA',     value: '22.1x' },
  { label: 'Rev Growth',    value: '+5.2%', subValue: 'YoY' },
  { label: 'ROE',           value: '156.8%' },
  { label: 'Div Yield',     value: '0.55%' },
];

interface QuarterlyFinancial {
  period: string;
  revenue: number;
  netIncome: number;
  eps: number;
}

const quarterlyData: QuarterlyFinancial[] = [
  { period: 'Q1 2026', revenue: 119500, netIncome: 33916, eps: 2.18 },
  { period: 'Q4 2025', revenue: 94930,  netIncome: 24780, eps: 1.64 },
  { period: 'Q3 2025', revenue: 85777,  netIncome: 22956, eps: 1.46 },
  { period: 'Q2 2025', revenue: 81797,  netIncome: 21448, eps: 1.40 },
];

interface QualityScoreItem {
  name: string;
  value: number;
  maxValue: number;
  classification: string;
}

const qualityScores: QualityScoreItem[] = [
  { name: 'Piotroski F-Score', value: 7, maxValue: 9, classification: 'Strong' },
  { name: 'Altman Z-Score',    value: 5.82, maxValue: 10, classification: 'Safe' },
  { name: 'Composite Quality', value: 82, maxValue: 100, classification: 'Excellent' },
];

interface NewsItem {
  id: string;
  headline: string;
  source: string;
  time: string;
}

const newsItems: NewsItem[] = [
  { id: '1', headline: 'Apple Vision Pro sales exceed expectations in Q1', source: 'Bloomberg', time: '2h ago' },
  { id: '2', headline: 'Apple expands AI chip partnership with TSMC',      source: 'Reuters',   time: '4h ago' },
  { id: '3', headline: 'Services revenue hits record $24.2B in quarter',   source: 'CNBC',      time: '6h ago' },
  { id: '4', headline: 'Apple Car project timeline pushed to 2028',        source: 'WSJ',       time: '1d ago' },
  { id: '5', headline: 'App Store antitrust ruling appeal filed',          source: 'FT',        time: '1d ago' },
];

// --- Helpers -----------------------------------------------------------------

function formatM(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}B`;
  return `$${n.toFixed(0)}M`;
}

// --- Component ---------------------------------------------------------------

export default function CompanyOverview() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Company Header */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {company.name}
        </h1>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>
          {company.ticker}
        </span>
        <span style={{ ...labelStyle }}>{company.exchange}</span>
        <span style={{ ...labelStyle }}>|</span>
        <span style={{ ...labelStyle }}>{company.sector}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            ${company.price.toFixed(2)}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-md)', fontWeight: 500, color: signalColor(company.changePct) }}>
            {company.changePct >= 0 ? '+' : ''}{company.changePct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {kpis.map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              {kpi.value}
            </div>
            {kpi.subValue && (
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                {kpi.subValue}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 2-column body */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Price Chart Placeholder */}
          <div style={{
            ...panelStyle,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '200px',
            borderStyle: 'dashed',
          }}>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: 'var(--color-text-tertiary)' }}>
              Price Chart &mdash; Coming Soon
            </span>
          </div>

          {/* Financial Summary */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Quarterly Financials</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Period', 'Revenue', 'Net Income', 'EPS'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Period' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {quarterlyData.map((q) => (
                  <tr key={q.period} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{q.period}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatM(q.revenue)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatM(q.netIncome)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${q.eps.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Quality Scores */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Quality Scores</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
              {qualityScores.map((s) => {
                const pct = (s.value / s.maxValue) * 100;
                return (
                  <div key={s.name} style={{ textAlign: 'center' }}>
                    <div style={{ ...labelStyle, marginBottom: '6px' }}>{s.name}</div>
                    <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-2xl)', fontWeight: 600, color: qualityColor(s.value) }}>
                      {s.value}
                    </div>
                    {/* Bar */}
                    <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px', marginTop: '6px' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: qualityColor(s.value), borderRadius: '2px' }} />
                    </div>
                    <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '4px' }}>
                      {s.classification}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* News Feed */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>News</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {newsItems.map((n) => (
                <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.4 }}>
                    {n.headline}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '2px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)' }}>{n.source}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{n.time}</span>
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
