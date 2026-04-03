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

// --- Default empty data (populated by API) -----------------------------------

const filings: any[] = [];

function filingBadgeColor(type: string): string {
  if (type === '10-K') return 'var(--color-accent-primary)';
  if (type === '10-Q') return 'var(--color-signal-neutral)';
  return 'var(--color-signal-warning)';
}

// Legacy inline data kept for reference (now handled by component props)
// const insiderTransactions = [...];
// const filingDiffs = [...];

// --- Default empty data (populated by API) -----------------------------------

const insiderTxData: InsiderTransaction[] = [];

const insiderSignals: InsiderSignal[] = [];

const diffSections: DiffSection[] = [];

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
        <p style={{ ...labelStyle, marginTop: '4px' }}>{primary?.ticker ?? '—'} &mdash; {primary?.name ?? '—'}</p>
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
          <p style={labelStyle}>No risk factor data available. Select a security to load filings.</p>
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
          <p style={labelStyle}>No MD&A data available. Select a security to load filings.</p>
        )}
      </div>
    </div>
  );
}
