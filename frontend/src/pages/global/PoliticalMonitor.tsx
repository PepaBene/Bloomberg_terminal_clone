// ---------------------------------------------------------------------------
// Political Monitor Dashboard
//
// Honesty pass: the previous version mapped a SINGLE geopolitical-events hook
// (useGeopoliticalEvents) onto all four tabs — bills, regulations, sanctions
// and elections — with completely mismatched fields, plus silent mock
// fallbacks (`eventsData ?? MOCK`).
//
// Each tab is now wired to its own real backend endpoint:
//   - Legislation -> GET /v3/global/political/us/bills
//   - Regulatory  -> GET /v3/global/political/us/regulations
//   - Sanctions   -> GET /v3/global/political/sanctions
//   - Elections   -> GET /v3/global/political/elections
// Fields are mapped from the real response schemas and each tab shows an honest
// empty state when it has no rows. (The SanctionsTable component is not used
// here because it requires programs/targets/trajectory aggregates the sanctions
// endpoint does not provide — individual entries are shown instead of fabricated
// aggregates.)
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { BillTracker } from '@/components/global';
import type { BillRecord } from '@/components/global';
import { EmptyState } from '@/components/feedback';

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

function severityColor(severity: string): string {
  switch (severity.toUpperCase()) {
    case 'CRITICAL': return '#dc2626';
    case 'HIGH':     return 'var(--color-signal-negative)';
    case 'MEDIUM':   return 'var(--color-quality-2)';
    case 'LOW':      return 'var(--color-quality-4)';
    default:         return 'var(--color-text-secondary)';
  }
}

// --- DTOs (mirror backend response schemas) ----------------------------------

interface LegislativeBillDTO {
  bill_id: string;
  title: string;
  summary?: string | null;
  bill_type?: string | null;
  status?: string | null;
  sponsor_count?: number | null;
  passage_probability?: number | null; // 0-100
  affected_sectors?: string[] | Record<string, unknown> | null;
  introduced_date?: string | null;
  last_action_date?: string | null;
}

interface RegulatoryActionDTO {
  id: string;
  agency?: string | null;
  action_type?: string | null;
  title: string;
  description?: string | null;
  severity?: string | null;
  action_date?: string | null;
}

interface SanctionsEntryDTO {
  id: string;
  program?: string | null;
  country_code?: string | null;
  target_name?: string | null;
  target_type?: string | null;
  status?: string | null;
  effective_date?: string | null;
  description?: string | null;
}

interface ElectionDTO {
  id: string;
  title: string;
  description?: string | null;
  countries_involved?: string[] | null;
  election_date?: string | null;
  severity?: string | null;
}

type SectionTab = 'Legislation' | 'Regulatory' | 'Sanctions' | 'Elections';
const tabs: SectionTab[] = ['Legislation', 'Regulatory', 'Sanctions', 'Elections'];

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

// --- Component ---------------------------------------------------------------

export default function PoliticalMonitor() {
  const [activeTab, setActiveTab] = useState<SectionTab>('Legislation');

  const { data: billsRaw, isLoading: loadingBills } = useQuery({
    queryKey: ['political', 'us-bills'],
    enabled: activeTab === 'Legislation',
    retry: 0,
    queryFn: () => api.get<LegislativeBillDTO[]>('/v3/global/political/us/bills', { limit: 50 }),
  });
  const billRecords: BillRecord[] = (Array.isArray(billsRaw) ? billsRaw : []).map((b) => ({
    id: b.bill_id,
    title: b.title,
    type: b.bill_type ?? 'Bill',
    status: b.status ?? 'Unknown',
    sponsors: b.sponsor_count ?? 0,
    passageProbability: b.passage_probability ?? 0,
    affectedSectors: asStringList(b.affected_sectors),
    lastAction: b.last_action_date ?? b.introduced_date ?? '—',
  }));

  const { data: regsRaw, isLoading: loadingRegs } = useQuery({
    queryKey: ['political', 'us-regulations'],
    enabled: activeTab === 'Regulatory',
    retry: 0,
    queryFn: () => api.get<RegulatoryActionDTO[]>('/v3/global/political/us/regulations', { limit: 50 }),
  });
  const regulatoryActions = Array.isArray(regsRaw) ? regsRaw : [];

  const { data: sanctionsRaw, isLoading: loadingSanctions } = useQuery({
    queryKey: ['political', 'sanctions'],
    enabled: activeTab === 'Sanctions',
    retry: 0,
    queryFn: () => api.get<SanctionsEntryDTO[]>('/v3/global/political/sanctions', { limit: 100 }),
  });
  const sanctions = Array.isArray(sanctionsRaw) ? sanctionsRaw : [];

  const { data: electionsRaw, isLoading: loadingElections } = useQuery({
    queryKey: ['political', 'elections'],
    enabled: activeTab === 'Elections',
    retry: 0,
    queryFn: () => api.get<ElectionDTO[]>('/v3/global/political/elections'),
  });
  const elections = Array.isArray(electionsRaw) ? electionsRaw : [];

  const thStyle: React.CSSProperties = {
    ...labelStyle,
    textAlign: 'left',
    padding: 'var(--table-cell-py) var(--table-cell-px)',
    borderBottom: '1px solid var(--color-surface-border)',
    whiteSpace: 'nowrap',
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Political Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Legislative bills, regulatory actions, sanctions, and election monitoring
        </p>
      </div>

      {/* Section Tabs */}
      <div style={{
        ...panelStyle,
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        marginBottom: 'var(--panel-gap)',
        padding: '4px 8px',
      }}>
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 14px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: activeTab === tab ? 600 : 400,
              background: activeTab === tab ? 'var(--color-surface-overlay)' : 'transparent',
              color: activeTab === tab ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Legislation Tab - BillTracker cards */}
      {activeTab === 'Legislation' && (
        loadingBills ? (
          <div style={panelStyle}><EmptyState icon="⏳" title="Loading bills…" /></div>
        ) : billRecords.length === 0 ? (
          <div style={panelStyle}>
            <EmptyState icon="🏛️" title="No legislative bills" description="No market-moving bills have been ingested." />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)' }}>
            {billRecords.map((bill) => (
              <BillTracker key={bill.id} bill={bill} />
            ))}
          </div>
        )
      )}

      {/* Regulatory Tab */}
      {activeTab === 'Regulatory' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Regulatory Actions</h2>
          {loadingRegs ? (
            <EmptyState icon="⏳" title="Loading regulations…" />
          ) : regulatoryActions.length === 0 ? (
            <EmptyState icon="⚖️" title="No regulatory actions" description="No active regulatory rulemaking has been ingested." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Agency', 'Type', 'Title', 'Severity', 'Date'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {regulatoryActions.map((ra) => (
                  <tr key={ra.id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)', fontSize: 'var(--text-sm)' }}>{ra.agency ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.action_type ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.title}</td>
                    <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                      {ra.severity ? (
                        <span style={{
                          fontFamily: 'var(--font-ui)',
                          fontSize: 'var(--text-xs)',
                          padding: '1px 6px',
                          borderRadius: '2px',
                          color: severityColor(ra.severity),
                          background: `color-mix(in srgb, ${severityColor(ra.severity)} 15%, transparent)`,
                          fontWeight: 600,
                        }}>
                          {ra.severity}
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.action_date ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Sanctions Tab */}
      {activeTab === 'Sanctions' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Active Sanctions Entries</h2>
          {loadingSanctions ? (
            <EmptyState icon="⏳" title="Loading sanctions…" />
          ) : sanctions.length === 0 ? (
            <EmptyState icon="🚫" title="No sanctions entries" description="No sanctions entries have been ingested." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Program', 'Country', 'Target', 'Type', 'Status', 'Effective'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sanctions.map((s) => (
                  <tr key={s.id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)', fontSize: 'var(--text-sm)' }}>{s.program ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.country_code ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.target_name ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.target_type ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.status ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.effective_date ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Elections Tab */}
      {activeTab === 'Elections' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Upcoming Elections</h2>
          {loadingElections ? (
            <EmptyState icon="⏳" title="Loading elections…" />
          ) : elections.length === 0 ? (
            <EmptyState icon="🗳️" title="No elections" description="No upcoming elections have been ingested." />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Event', 'Countries', 'Date', 'Market Impact'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {elections.map((e) => {
                  const impact = e.severity ?? '';
                  const impactColor = severityColor(impact);
                  return (
                    <tr key={e.id} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{e.title}</td>
                      <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{asStringList(e.countries_involved).join(', ') || '—'}</td>
                      <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.election_date ?? '—'}</td>
                      <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                        {impact ? (
                          <span style={{
                            fontFamily: 'var(--font-ui)',
                            fontSize: 'var(--text-xs)',
                            padding: '1px 6px',
                            borderRadius: '2px',
                            color: impactColor,
                            background: `color-mix(in srgb, ${impactColor} 15%, transparent)`,
                            fontWeight: 600,
                          }}>
                            {impact}
                          </span>
                        ) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
