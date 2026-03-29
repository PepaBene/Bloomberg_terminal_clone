// ---------------------------------------------------------------------------
// Filings View — SEC Filings Table, Filing Diff, Insider Transactions
// ---------------------------------------------------------------------------
import { FilingDiffViewer, InsiderActivityTable } from '@/components/intelligence';
import type { InsiderTransaction, InsiderSignal, DiffSection } from '@/components/intelligence';

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

// Legacy inline data kept for reference (now handled by component props)
// const insiderTransactions = [...];
// const filingDiffs = [...];

// --- Component Data ----------------------------------------------------------

const insiderTxData: InsiderTransaction[] = [
  { id: 'tx1', date: '2026-03-15', insiderName: 'Tim Cook', title: 'CEO', type: 'SELL', shares: 50000, price: 182.40, value: 9120000 },
  { id: 'tx2', date: '2026-03-02', insiderName: 'Luca Maestri', title: 'SVP, CFO', type: 'SELL', shares: 25000, price: 179.85, value: 4496250 },
  { id: 'tx3', date: '2026-02-14', insiderName: 'Jeff Williams', title: 'COO', type: 'BUY', shares: 10000, price: 174.20, value: 1742000 },
  { id: 'tx4', date: '2026-01-22', insiderName: "Deirdre O'Brien", title: 'SVP Retail', type: 'SELL', shares: 15000, price: 176.30, value: 2644500 },
];

const insiderSignals: InsiderSignal[] = [
  { transactionId: 'tx3', signal: 'CEO_PURCHASE', severity: 'positive' },
  { transactionId: 'tx1', signal: 'UNUSUAL_SALE', severity: 'negative' },
];

const diffSections: DiffSection[] = [
  {
    name: 'Risk Factors',
    prior: 'The Company is subject to risks relating to product quality...\nOperating in highly competitive markets...',
    current: 'The Company is subject to risks relating to product quality and AI integration...\nOperating in highly competitive markets with evolving regulatory landscape...',
    changes: [
      { type: 'add', text: 'Added language regarding AI-related regulatory risks and model governance requirements.' },
      { type: 'modify', text: 'Expanded competitive landscape to include generative AI market participants.' },
    ],
  },
  {
    name: "MD&A",
    prior: 'Revenue increased 5% driven by Services growth.\nGross margin expanded 120 bps year-over-year.',
    current: 'Revenue increased 8% driven by Services and Vision Pro.\nGross margin expanded 180 bps driven by mix shift to Services.',
    changes: [
      { type: 'modify', text: 'Revenue growth attribution updated to include Vision Pro as a growth driver.' },
      { type: 'modify', text: 'Gross margin expansion explanation changed from 120 bps to 180 bps.' },
      { type: 'add', text: 'New disclosure on spatial computing market opportunity and investment plans.' },
    ],
  },
];

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

          {/* Insider Transactions — powered by InsiderActivityTable */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Insider Transactions</h2>
            <InsiderActivityTable transactions={insiderTxData} signals={insiderSignals} />
          </div>
        </div>

        {/* Right — Filing Diff — powered by FilingDiffViewer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          <div style={panelStyle}>
            <h2 style={sectionTitle}>10-K Diff: FY2025 vs FY2024</h2>
            <p style={{ ...labelStyle, marginBottom: '12px' }}>Material section changes detected</p>
            <FilingDiffViewer sections={diffSections} mode="side-by-side" />
          </div>
        </div>
      </div>
    </div>
  );
}
