// ---------------------------------------------------------------------------
// Filings View — SEC Filings Table, Filing Diff, Insider Transactions
// ---------------------------------------------------------------------------
import { FilingDiffViewer, InsiderActivityTable } from '@/components/intelligence';
import type { InsiderTransaction, InsiderSignal, DiffSection } from '@/components/intelligence';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useFilingEvents, useFilingDiffs, useFilingInsiders, useFilingRiskFactors, useFilingMDNA } from '@/hooks';

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
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const { data: apiFilings } = useFilingEvents(resolvedId);
  const { data: apiDiffs } = useFilingDiffs(resolvedId);
  const { data: apiInsiders } = useFilingInsiders(resolvedId);
  const { data: apiRiskFactors } = useFilingRiskFactors(resolvedId);
  const { data: apiMDNA } = useFilingMDNA(resolvedId);

  const activeFilings = (apiFilings as any[]) ?? filings;
  const activeDiffs = (apiDiffs as any)?.sections ?? diffSections;
  const activeInsiders = (apiInsiders as any)?.transactions ?? insiderTxData;
  const activeSignals = (apiInsiders as any)?.signals ?? insiderSignals;

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
                {activeFilings.map((f: any, i: number) => (
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
            <InsiderActivityTable transactions={activeInsiders} signals={activeSignals} />
          </div>
        </div>

        {/* Right — Filing Diff — powered by FilingDiffViewer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
          <div style={panelStyle}>
            <h2 style={sectionTitle}>10-K Diff: FY2025 vs FY2024</h2>
            <p style={{ ...labelStyle, marginBottom: '12px' }}>Material section changes detected</p>
            <FilingDiffViewer sections={activeDiffs} mode="side-by-side" />
          </div>
        </div>
      </div>

      {/* Risk Factors */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Risk Factors Summary</h2>
        {apiRiskFactors ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(apiRiskFactors as any[]).map((rf: any, i: number) => (
              <div key={i} style={{ padding: '10px', background: 'var(--color-surface-raised)', borderRadius: '4px', borderLeft: `3px solid ${rf.severity === 'high' ? 'var(--color-signal-negative)' : rf.severity === 'medium' ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)'}` }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '4px' }}>{rf.title ?? rf.category}</div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{rf.summary ?? rf.description}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { title: 'Regulatory & Antitrust Risk', severity: 'high', summary: 'Multiple jurisdictions pursuing antitrust actions against App Store practices. EU DMA compliance costs estimated at $500M+.' },
              { title: 'China Revenue Concentration', severity: 'high', summary: 'Greater China represents ~19% of revenue. Geopolitical tensions and local competition from Huawei pose ongoing risk.' },
              { title: 'AI Integration Execution', severity: 'medium', summary: 'Delayed AI feature rollout relative to competitors. On-device AI strategy may limit capability vs cloud-first approaches.' },
              { title: 'Supply Chain Concentration', severity: 'medium', summary: 'Heavy reliance on TSMC for advanced chips. Any disruption to Taiwan manufacturing could impact production.' },
            ].map((rf, i) => (
              <div key={i} style={{ padding: '10px', background: 'var(--color-surface-raised)', borderRadius: '4px', borderLeft: `3px solid ${rf.severity === 'high' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)'}` }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '4px' }}>{rf.title}</div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{rf.summary}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* MD&A Highlights */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>MD&A Highlights</h2>
        {apiMDNA ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {(apiMDNA as any[]).map((item: any, i: number) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-text-primary)' }}>{item.topic}</div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginTop: '4px', lineHeight: 1.5 }}>{item.summary}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { topic: 'Revenue Growth Drivers', summary: 'Services segment grew 14.1% YoY to $96B, now 22.8% of revenue. iPhone revenue grew modestly at 3.8% driven by Pro models and emerging markets.' },
              { topic: 'Margin Expansion', summary: 'Gross margin expanded 180bps to 45.3% driven by mix shift toward higher-margin Services. Operating leverage improving as R&D growth decelerates.' },
              { topic: 'Capital Return', summary: 'Returned $105.3B to shareholders through $90.1B in buybacks and $15.2B in dividends. Net cash position declined to $49B from $58B.' },
              { topic: 'Emerging Opportunities', summary: 'Vision Pro launched with revenue tracking above internal forecasts. Apple Intelligence features rolled out across product line. India revenue growth exceeding 25%.' },
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-text-primary)' }}>{item.topic}</div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginTop: '4px', lineHeight: 1.5 }}>{item.summary}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
