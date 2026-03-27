// ---------------------------------------------------------------------------
// Company Intelligence — Business Model, Capital Allocation, Management Quality
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

function qualityColor(score: number): string {
  if (score >= 8) return 'var(--color-quality-5)';
  if (score >= 6) return 'var(--color-quality-4)';
  if (score >= 4) return 'var(--color-quality-3)';
  if (score >= 2) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

function riskColor(level: string): string {
  if (level === 'Low') return 'var(--color-signal-positive)';
  if (level === 'Medium') return 'var(--color-signal-warning)';
  return 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const businessModel = [
  { segment: 'iPhone', revPct: 52.1, marginPct: 42.3, growth: 3.8 },
  { segment: 'Services', revPct: 22.8, marginPct: 71.2, growth: 14.1 },
  { segment: 'Mac', revPct: 9.7, marginPct: 31.5, growth: -1.2 },
  { segment: 'iPad', revPct: 6.8, marginPct: 35.1, growth: 5.4 },
  { segment: 'Wearables & Accessories', revPct: 8.6, marginPct: 28.7, growth: -3.5 },
];

const capitalAllocation = [
  { year: 'FY2025', capex: 11.0, rnd: 30.7, buybacks: 90.1, dividends: 15.2, debtRepay: 9.7 },
  { year: 'FY2024', capex: 10.8, rnd: 29.0, buybacks: 77.6, dividends: 15.0, debtRepay: 11.5 },
  { year: 'FY2023', capex: 10.9, rnd: 26.3, buybacks: 77.5, dividends: 14.8, debtRepay: 16.0 },
];

const managementScores = [
  { metric: 'Capital Allocation', score: 9.1, maxScore: 10 },
  { metric: 'Execution Consistency', score: 8.7, maxScore: 10 },
  { metric: 'Shareholder Alignment', score: 8.9, maxScore: 10 },
  { metric: 'Strategic Vision', score: 7.8, maxScore: 10 },
  { metric: 'Governance Quality', score: 8.2, maxScore: 10 },
];

const balanceSheetRisk = [
  { metric: 'Net Debt / EBITDA', value: '0.4x', risk: 'Low' },
  { metric: 'Interest Coverage', value: '29.3x', risk: 'Low' },
  { metric: 'Current Ratio', value: '0.99', risk: 'Medium' },
  { metric: 'Debt Maturity (wt avg)', value: '7.2 yrs', risk: 'Low' },
  { metric: 'Pension Underfunding', value: 'N/A', risk: 'Low' },
];

// --- Component ---------------------------------------------------------------

export default function CompanyIntelligence() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Company Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Business Model Breakdown */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Business Model Breakdown</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Segment', 'Rev %', 'Margin %', 'Growth %'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Segment' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {businessModel.map((s) => (
                <tr key={s.segment} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.segment}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.revPct.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.marginPct.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: s.growth >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                    {s.growth >= 0 ? '+' : ''}{s.growth.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Capital Allocation */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Capital Allocation ($B)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Year', 'CapEx', 'R&D', 'Buybacks', 'Dividends', 'Debt Repay'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Year' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {capitalAllocation.map((r) => (
                <tr key={r.year} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.year}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.capex.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.rnd.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.buybacks.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.dividends.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.debtRepay.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Management Quality Scores */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Management Quality</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {managementScores.map((m) => {
              const pct = (m.score / m.maxScore) * 100;
              return (
                <div key={m.metric}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={labelStyle}>{m.metric}</span>
                    <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600, color: qualityColor(m.score) }}>{m.score.toFixed(1)}</span>
                  </div>
                  <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: qualityColor(m.score), borderRadius: '2px' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Balance Sheet Risk */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Balance Sheet Risk</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Metric', 'Value', 'Risk'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {balanceSheetRisk.map((r) => (
                <tr key={r.metric} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.metric}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.value}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: riskColor(r.risk), fontWeight: 500 }}>{r.risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
