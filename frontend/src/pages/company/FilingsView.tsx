// ---------------------------------------------------------------------------
// Filings View — SEC Filings Table, Filing Diff, Insider Transactions
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

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const filings = [
  { date: '2026-02-28', type: '10-K', period: 'FY2025', description: 'Annual report', pages: 142 },
  { date: '2026-01-31', type: '10-Q', period: 'Q1 2026', description: 'Quarterly report', pages: 68 },
  { date: '2026-01-15', type: '8-K', period: 'N/A', description: 'Earnings press release', pages: 12 },
  { date: '2025-10-30', type: '10-Q', period: 'Q4 2025', description: 'Quarterly report', pages: 71 },
  { date: '2025-10-02', type: '8-K', period: 'N/A', description: 'Leadership change announcement', pages: 4 },
];

function filingBadgeColor(type: string): string {
  if (type === '10-K') return 'var(--color-accent-primary)';
  if (type === '10-Q') return 'var(--color-signal-neutral)';
  return 'var(--color-signal-warning)';
}

const insiderTransactions = [
  { date: '2026-03-15', insider: 'Tim Cook', title: 'CEO', txType: 'Sale', shares: 50000, price: 182.40, value: 9120000 },
  { date: '2026-03-02', insider: 'Luca Maestri', title: 'SVP, CFO', txType: 'Sale', shares: 25000, price: 179.85, value: 4496250 },
  { date: '2026-02-14', insider: 'Jeff Williams', title: 'COO', txType: 'Purchase', shares: 10000, price: 174.20, value: 1742000 },
  { date: '2026-01-22', insider: 'Deirdre O\'Brien', title: 'SVP Retail', txType: 'Sale', shares: 15000, price: 176.30, value: 2644500 },
];

const filingDiffs = [
  { section: 'Risk Factors', changes: 12, added: 3, removed: 1 },
  { section: 'Revenue Recognition', changes: 4, added: 1, removed: 0 },
  { section: 'Liquidity & Capital', changes: 7, added: 2, removed: 2 },
  { section: 'Legal Proceedings', changes: 9, added: 4, removed: 1 },
];

function formatCurrency(n: number): string {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

// --- Component ---------------------------------------------------------------

export default function FilingsView() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          SEC Filings &amp; Insider Activity
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          {/* Recent Filings */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Recent Filings</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Type', 'Period', 'Description', 'Pages'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Pages' ? 'right' : 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filings.map((f, i) => (
                  <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{f.date}</td>
                    <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: filingBadgeColor(f.type), background: 'var(--color-surface-overlay)', padding: '2px 6px', borderRadius: '3px' }}>{f.type}</span>
                    </td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{f.period}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.description}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{f.pages}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Insider Transactions */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Insider Transactions</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Insider', 'Title', 'Type', 'Shares', 'Price', 'Value'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: ['Shares', 'Price', 'Value'].includes(h) ? 'right' : 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {insiderTransactions.map((t, i) => (
                  <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{t.date}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{t.insider}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.title}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: t.txType === 'Purchase' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 500 }}>{t.txType}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.shares.toLocaleString()}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${t.price.toFixed(2)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{formatCurrency(t.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right — Filing Diff */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>10-K Diff: FY2025 vs FY2024</h2>
          <p style={{ ...labelStyle, marginBottom: '12px' }}>Material section changes detected</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {filingDiffs.map((d) => (
              <div key={d.section} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: '4px' }}>{d.section}</div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>{d.changes} changes</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>+{d.added} added</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)' }}>-{d.removed} removed</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
