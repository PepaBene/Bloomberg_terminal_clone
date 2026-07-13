// ---------------------------------------------------------------------------
// Filings View — SEC Filings Table, Filing Diff, Insider Transactions
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { FilingDiffViewer, InsiderActivityTable } from '@/components/intelligence';
import type { InsiderTransaction, InsiderSignal, DiffSection, DiffChange } from '@/components/intelligence';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useFilingEvents, useFilingDiffs, useFilingInsiders, useFilingRiskFactors, useFilingMDNA } from '@/hooks';

// --- API response shapes (subset of backend schemas actually read) ---------
// Mirrors `EightKEventsListResponse`/`EightKEventResponse`
// (src/schemas/filing_intelligence.py:9,26) — `{events: [...], total_count}`,
// not a bare array.
interface FilingEventApi {
  id: string;
  filing_date: string;
  item_number: string;
  item_description: string | null;
  ai_summary: string | null;
}
interface FilingEventsListApi {
  events?: FilingEventApi[];
}

// Mirrors `FilingDiffResponse`/`FilingDiffSectionResponse` (:31,46) —
// `{section_diffs: [...]}`, not `{sections: [...]}`.
interface FilingDiffParagraphApi {
  text?: string;
  [key: string]: unknown;
}
interface FilingDiffSectionApi {
  section_key: string;
  section_name: string | null;
  classification: string | null;
  materiality: string | null;
  added_paragraphs: FilingDiffParagraphApi[] | null;
  removed_paragraphs: FilingDiffParagraphApi[] | null;
  modified_paragraphs: FilingDiffParagraphApi[] | null;
}
interface FilingDiffResponseApi {
  section_diffs?: FilingDiffSectionApi[];
}

// Mirrors `InsiderSummaryResponse`/`InsiderTransactionResponse`/`InsiderSignalResponse`
// (src/schemas/insider_intelligence.py:8,25,34) — the transactions field is
// `recent_transactions`, not `transactions`.
interface InsiderTransactionApi {
  id: string;
  reporting_person: string;
  relationship: string;
  transaction_type: string;
  transaction_date: string;
  shares: number | null;
  price_per_share: number | null;
  total_value: number | null;
}
interface InsiderSignalApi {
  signal_type: string;
  signal_strength: number;
}
interface InsiderSummaryApi {
  signals?: InsiderSignalApi[];
  recent_transactions?: InsiderTransactionApi[];
}

// `FilingDiffResponse` shape again — used for the (mislabeled) risk-factors
// diff endpoint (`/filings/{id}/diff/risk-factors`), same response model.
interface RiskFactorSectionApi {
  section_key: string;
  section_name: string | null;
  change_pct: number | null;
  materiality: string | null;
  added_count: number;
  removed_count: number;
  modified_count: number;
}
interface RiskFactorsDiffApi {
  section_diffs?: RiskFactorSectionApi[];
}

// [P1-FP-010 note] `GET /v3/filings/{id}/mdna` (what `useFilingMDNA` calls)
// does not exist anywhere in `filing_intelligence.py` — no known real
// endpoint backs "MD&A Highlights" today. Typed defensively so a future
// backend response degrades gracefully instead of crashing; the panel keeps
// its existing honest "No MD&A data available" empty state.
interface MDNAItemApi {
  topic?: string;
  summary?: string;
  [key: string]: unknown;
}

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

interface FilingRow {
  date: string;
  type: string;
  period: string;
  description: string;
  pages: number | null;
}

const filings: FilingRow[] = [];

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

  const { data: apiFilings, isLoading: filingsLoading, isError: filingsError } = useFilingEvents(resolvedId) as { data: FilingEventsListApi | undefined; isLoading: boolean; isError: boolean };
  const { data: apiDiffs, isLoading: diffsLoading, isError: diffsError } = useFilingDiffs(resolvedId) as { data: FilingDiffResponseApi | undefined; isLoading: boolean; isError: boolean };
  const { data: apiInsiders, isLoading: insidersLoading, isError: insidersError } = useFilingInsiders(resolvedId) as { data: InsiderSummaryApi | undefined; isLoading: boolean; isError: boolean };
  const { data: apiRiskFactors, isLoading: riskLoading, isError: riskError } = useFilingRiskFactors(resolvedId) as { data: RiskFactorsDiffApi | undefined; isLoading: boolean; isError: boolean };
  const { data: apiMDNA, isLoading: mdnaLoading, isError: mdnaError } = useFilingMDNA(resolvedId) as { data: MDNAItemApi[] | { items?: MDNAItemApi[] } | undefined; isLoading: boolean; isError: boolean };

  const isLoading = filingsLoading || diffsLoading || insidersLoading || riskLoading || mdnaLoading;
  const isError = filingsError || diffsError || insidersError || riskError || mdnaError;

  if (isLoading) return <div style={{ padding: '16px' }}>Loading filing intelligence...</div>;
  if (isError) return <div style={{ padding: '16px', color: 'var(--color-signal-negative)' }}>Failed to load filing intelligence.</div>;

  // [P1-FP-010 fix] `EightKEventsListResponse` is `{events: [...], total_count}`,
  // not a bare array. Field names differ from the "Recent Filings" table's
  // original camelCase assumption too — map the real 8-K event fields
  // (`filing_date`, `item_number`, `item_description`/`ai_summary`) rather
  // than fabricating `period`/`pages`, which this endpoint doesn't provide.
  const activeFilings: FilingRow[] = useMemo(() => {
    const events = apiFilings?.events;
    if (!Array.isArray(events) || events.length === 0) return filings;
    return events.map((e) => ({
      date: e.filing_date,
      type: e.item_number,
      period: '',
      description: e.item_description ?? e.ai_summary ?? '',
      pages: null,
    }));
  }, [apiFilings]);

  // [P1-FP-010 fix] `FilingDiffResponse` carries `section_diffs`, not
  // `sections`, and each section has counts/classification rather than full
  // prior/current text — the backend never returns full paragraph text for
  // "prior"/"current", so those are left empty (not fabricated) while the
  // real per-paragraph add/remove/modify counts still drive the change list.
  const activeDiffs: DiffSection[] = useMemo(() => {
    const rows = apiDiffs?.section_diffs;
    if (!Array.isArray(rows) || rows.length === 0) return diffSections;
    const toChanges = (paras: FilingDiffParagraphApi[] | null | undefined, type: DiffChange['type'], fallback: string): DiffChange[] =>
      (paras ?? []).map((p) => ({ type, text: p.text ?? fallback }));
    return rows.map((s) => ({
      name: s.section_name ?? s.section_key,
      prior: '',
      current: '',
      changes: [
        ...toChanges(s.added_paragraphs, 'add', 'Paragraph added'),
        ...toChanges(s.removed_paragraphs, 'remove', 'Paragraph removed'),
        ...toChanges(s.modified_paragraphs, 'modify', 'Paragraph modified'),
      ],
    }));
  }, [apiDiffs]);

  // [P1-FP-010 fix] `InsiderSummaryResponse` carries `recent_transactions`
  // (not `transactions`) with snake_case field names.
  const activeInsiders: InsiderTransaction[] = useMemo(() => {
    const rows = apiInsiders?.recent_transactions;
    if (!Array.isArray(rows) || rows.length === 0) return insiderTxData;
    return rows.map((t) => ({
      id: t.id,
      date: t.transaction_date,
      insiderName: t.reporting_person,
      title: t.relationship,
      type: (t.transaction_type?.toUpperCase() as InsiderTransaction['type']) ?? 'BUY',
      shares: t.shares ?? 0,
      price: t.price_per_share ?? 0,
      value: t.total_value ?? 0,
    }));
  }, [apiInsiders]);

  const activeSignals: InsiderSignal[] = useMemo(() => {
    const rows = apiInsiders?.signals;
    if (!Array.isArray(rows) || rows.length === 0) return insiderSignals;
    return rows.map((s, i) => ({
      transactionId: `${s.signal_type}-${i}`,
      signal: s.signal_type,
      severity: s.signal_strength > 0 ? 'positive' : s.signal_strength < 0 ? 'negative' : 'neutral',
    }));
  }, [apiInsiders]);

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
                {activeFilings.map((f, i: number) => (
                  <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{f.date}</td>
                    <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: filingBadgeColor(f.type), background: 'var(--color-surface-overlay)', padding: '2px 6px', borderRadius: '3px' }}>{f.type}</span>
                    </td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{f.period}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.description}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{f.pages ?? '—'}</td>
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
      {/* [P1-FP-010 fix] The (path-corrected) risk-factors-diff endpoint
          returns the same `FilingDiffResponse` shape as the main filing diff
          (`section_diffs` with counts/materiality/classification, not a
          per-factor `{title, summary, severity}` list) — map the real fields
          instead of assuming a shape the backend never returns. */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Risk Factors Summary</h2>
        {Array.isArray(apiRiskFactors?.section_diffs) && apiRiskFactors!.section_diffs!.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {apiRiskFactors!.section_diffs!.map((rf, i: number) => {
              const severity = (rf.materiality ?? '').toUpperCase();
              const borderColor =
                severity === 'HIGH' ? 'var(--color-signal-negative)' : severity === 'MEDIUM' ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)';
              return (
                <div key={i} style={{ padding: '10px', background: 'var(--color-surface-raised)', borderRadius: '4px', borderLeft: `3px solid ${borderColor}` }}>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '4px' }}>{rf.section_name ?? rf.section_key}</div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                    {rf.change_pct != null ? `${rf.change_pct.toFixed(1)}% change — ` : ''}
                    {rf.added_count} added, {rf.removed_count} removed, {rf.modified_count} modified
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={labelStyle}>No risk factor data available. Select a security to load filings.</p>
        )}
      </div>

      {/* MD&A Highlights */}
      {/* [P1-FP-010 note] No known backend endpoint currently backs this
          panel (`GET /v3/filings/{id}/mdna` doesn't exist in
          filing_intelligence.py) — kept defensively typed so it degrades to
          the existing honest empty state rather than crashing if a real
          response ever arrives in either shape. */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>MD&A Highlights</h2>
        {(() => {
          const mdnaItems: MDNAItemApi[] = Array.isArray(apiMDNA)
            ? apiMDNA
            : Array.isArray((apiMDNA as { items?: MDNAItemApi[] } | undefined)?.items)
              ? (apiMDNA as { items: MDNAItemApi[] }).items
              : [];
          return mdnaItems.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {mdnaItems.map((item, i: number) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-text-primary)' }}>{item.topic}</div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginTop: '4px', lineHeight: 1.5 }}>{item.summary}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={labelStyle}>No MD&A data available. Select a security to load filings.</p>
          );
        })()}
      </div>
    </div>
  );
}
