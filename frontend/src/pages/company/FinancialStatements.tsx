// ---------------------------------------------------------------------------
// Financial Statements — Income Statement, Balance Sheet, Cash Flow
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

function fmtM(n: number): string {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}B`;
  return `${n.toFixed(0)}M`;
}

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };
const periods = ['FY2025', 'FY2024', 'FY2023', 'FY2022'];

const incomeStatement = [
  { line: 'Revenue',            values: [391035, 383285, 383933, 394328], bold: false },
  { line: 'Cost of Revenue',    values: [214137, 210461, 214137, 223546], bold: false },
  { line: 'Gross Profit',       values: [176898, 172824, 169796, 170782], bold: true },
  { line: 'Operating Expenses', values: [56820, 54847, 53438, 51345], bold: false },
  { line: 'Operating Income',   values: [120078, 117977, 114301, 119437], bold: true },
  { line: 'Net Income',         values: [101100, 96995, 96995, 99803], bold: true },
];

const balanceSheet = [
  { line: 'Cash & Equivalents', values: [29965, 29965, 29965, 23646], bold: false },
  { line: 'Total Current Assets', values: [143566, 152987, 143566, 135405], bold: true },
  { line: 'Total Assets',       values: [352583, 364980, 352583, 352755], bold: true },
  { line: 'Total Current Liab', values: [145308, 153982, 145308, 153982], bold: true },
  { line: 'Long-Term Debt',     values: [98959, 95281, 98959, 98959], bold: false },
  { line: 'Total Equity',       values: [74100, 73812, 62146, 50672], bold: true },
];

const cashFlow = [
  { line: 'Operating CF',       values: [118254, 110543, 110543, 122151], bold: true },
  { line: 'Capital Expenditures', values: [-11000, -10959, -10959, -10708], bold: false },
  { line: 'Free Cash Flow',     values: [107254, 99584, 99584, 111443], bold: true },
  { line: 'Dividends Paid',     values: [-15200, -15025, -14841, -14841], bold: false },
  { line: 'Share Buybacks',     values: [-90100, -77550, -77550, -89402], bold: false },
];

function renderTable(title: string, rows: { line: string; values: number[]; bold: boolean }[]) {
  return (
    <div style={panelStyle}>
      <h2 style={sectionTitle}>{title}</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', width: '35%' }}>Line Item</th>
            {periods.map((p) => (
              <th key={p} style={{ ...labelStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.line} style={{ height: 'var(--table-row-height)' }}>
              <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: r.bold ? 600 : 400 }}>
                {r.line}
              </td>
              {r.values.map((v, i) => (
                <td key={i} style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: v < 0 ? 'var(--color-signal-negative)' : 'var(--color-text-primary)', fontWeight: r.bold ? 600 : 400 }}>
                  {fmtM(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Component ---------------------------------------------------------------

export default function FinancialStatements() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Financial Statements
        </h1>
        <span style={labelStyle}>{company.ticker} &mdash; {company.name}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          {['Annual', 'Quarterly'].map((t) => (
            <span key={t} style={{
              fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '4px 10px', borderRadius: '3px',
              background: t === 'Annual' ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
              color: t === 'Annual' ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
              cursor: 'pointer',
            }}>{t}</span>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {renderTable('Income Statement ($M)', incomeStatement)}
        {renderTable('Balance Sheet ($M)', balanceSheet)}
        {renderTable('Cash Flow Statement ($M)', cashFlow)}
      </div>
    </div>
  );
}
