// ---------------------------------------------------------------------------
// Governance Dashboard — Board, Compensation, Proxy, Shareholder Proposals
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useGovernance, useGovernanceBoard, useGovernanceCompensation, useGovernanceProxy, useShareholderProposals } from '@/hooks';

// --- API response shapes (subset of backend schemas actually read) ---------
// Mirrors `GovernanceAssessmentResponse`/`GovernanceRedFlagResponse`/
// `BoardMemberResponse`/`ExecutiveCompensationResponse`/
// `ShareholderProposalResponse` (src/schemas/governance_intelligence.py).

interface GovernanceRedFlagApi {
  flag: string;
  severity: string;
  detail: string;
}
interface GovernanceOverviewApi {
  governance_score: number;
  classification: string | null;
  red_flags: GovernanceRedFlagApi[];
  board_independence_pct: number | null;
  board_diversity_pct: number | null;
  ceo_is_chair: boolean;
}
interface BoardMemberApi {
  person_name: string;
  is_independent: boolean;
  is_chair: boolean;
  tenure_years: number | null;
  committees: string[] | null;
}
interface ExecutiveCompensationApi {
  person_name: string;
  role: string;
  total_compensation: number | null;
  base_salary: number | null;
  stock_awards: number | null;
}
interface ShareholderProposalApi {
  proposal_number: number;
  topic: string | null;
  management_recommendation: string | null;
  vote_for_pct: number | null;
  passed: boolean | null;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

function SkeletonBlock({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: '4px',
      }}
    />
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <SkeletonBlock width="260px" height="28px" />
      <div style={{ marginTop: '8px' }}><SkeletonBlock width="340px" height="16px" /></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', marginTop: '16px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <SkeletonBlock width="80px" height="14px" />
            <div style={{ marginTop: '8px' }}><SkeletonBlock width="50px" height="20px" /></div>
          </div>
        ))}
      </div>
      <div style={{ ...panelStyle, marginTop: '8px' }}><SkeletonBlock width="100%" height="40px" /></div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
        <div style={panelStyle}><SkeletonBlock width="100%" height="160px" /></div>
        <div style={panelStyle}><SkeletonBlock width="100%" height="160px" /></div>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ ...panelStyle, borderLeft: '3px solid var(--color-signal-negative)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', color: 'var(--color-signal-negative)' }}>!</span>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{message}</span>
      </div>
    </div>
  );
}

function EmptyTable({ message }: { message: string }) {
  return (
    <div style={{ padding: '16px', textAlign: 'center' }}>
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>{message}</span>
    </div>
  );
}

export default function GovernanceDashboard() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const { data: overview, isLoading: loadingGov, isError: errorGov } = useGovernance(resolvedId) as {
    data: GovernanceOverviewApi | undefined;
    isLoading: boolean;
    isError: boolean;
  };
  const { data: board, isLoading: loadingBoard, isError: errorBoard } = useGovernanceBoard(resolvedId) as {
    data: BoardMemberApi[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };
  const { data: compensation, isLoading: loadingComp, isError: errorComp } = useGovernanceCompensation(resolvedId) as {
    data: ExecutiveCompensationApi[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };
  const { data: _proxy, isLoading: _loadingProxy } = useGovernanceProxy(resolvedId);
  const { data: proposals, isLoading: loadingProposals, isError: errorProposals } = useShareholderProposals(resolvedId) as {
    data: ShareholderProposalApi[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const isLoading = loadingGov || loadingBoard || loadingComp || loadingProposals;
  const isError = errorGov && errorBoard && errorComp && errorProposals;

  if (isLoading) return <LoadingSkeleton />;
  if (isError) return <ErrorState message="Failed to load governance data. Please try again later." />;

  const gov = overview;
  const boardData = Array.isArray(board) ? board : [];
  const compData = Array.isArray(compensation) ? compensation : [];
  const proposalData = Array.isArray(proposals) ? proposals : [];

  // [P1-FP-016 fix] `GovernanceAssessmentResponse` has no `boardSize`/
  // `avgTenure`/`sayOnPayApproval` fields — those are derived client-side
  // from the real board roster (or shown as "--" when not derivable) instead
  // of reading nonexistent camelCase properties.
  const boardSize = boardData.length > 0 ? boardData.length : null;
  const tenureValues = boardData.map((d) => d.tenure_years).filter((t): t is number => t != null);
  const avgTenure = tenureValues.length > 0 ? tenureValues.reduce((a, b) => a + b, 0) / tenureValues.length : null;

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Corporate Governance
        </h1>
        <p style={labelStyle}>Board composition, compensation, and shareholder rights</p>
      </div>

      {/* KPI Row */}
      {/* [P1-FP-016 fix] `boardSize`/`avgTenure`/`sayOnPayApproval` don't
          exist on `GovernanceAssessmentResponse` \u2014 board size/tenure are
          derived from the real board roster above, and the "Say-on-Pay" slot
          (no backing data anywhere) is replaced with the real
          `governance_score`/`classification` fields instead of a fabricated
          percentage. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {[
          { label: 'Board Size', value: boardSize ?? '--' },
          { label: 'Independent %', value: gov?.board_independence_pct != null ? `${gov.board_independence_pct}%` : '--' },
          { label: 'Avg Tenure', value: avgTenure != null ? `${avgTenure.toFixed(1)} yrs` : '--' },
          { label: 'Gender Diversity', value: gov?.board_diversity_pct != null ? `${gov.board_diversity_pct}%` : '--' },
          { label: 'Governance Score', value: gov?.governance_score != null ? `${gov.governance_score}${gov.classification ? ` (${gov.classification})` : ''}` : '--' },
        ].map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={labelStyle}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', marginTop: '4px' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Governance Flags */}
      {/* [P1-FP-016 fix] `ceoChairSplit`/`annualElections`/`poisonPill`/
          `classifiedBoard` booleans don't exist on the backend response \u2014
          the real structured signal is `ceo_is_chair` (derived below) plus
          a free-form `red_flags` list (`GovernanceRedFlagResponse`), which
          is rendered directly instead of matching against fields that were
          never actually returned. */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Governance Provisions</h2>
        {gov ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: !gov.ceo_is_chair ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 700 }}>
                {!gov.ceo_is_chair ? '\u2713' : '\u2717'}
              </span>
              <span style={labelStyle}>CEO/Chair Separation</span>
            </div>
            {gov.red_flags.length === 0 ? (
              <p style={labelStyle}>No governance red flags reported</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {gov.red_flags.map((f, i) => (
                  <div key={i} style={{ padding: '8px 10px', background: 'var(--color-surface-raised)', borderRadius: '4px', borderLeft: `3px solid ${f.severity?.toUpperCase() === 'HIGH' ? 'var(--color-signal-negative)' : f.severity?.toUpperCase() === 'MEDIUM' ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)'}` }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{f.flag}</span>
                    <span style={{ ...labelStyle, marginLeft: '8px' }}>{f.detail}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <EmptyTable message="No governance data available" />
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Board */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Board of Directors</h2>
          {boardData.length === 0 ? (
            <EmptyTable message="No board data available" />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Name', 'Role', 'Independent', 'Tenure', 'Committees'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* [P1-FP-016 fix] `BoardMemberResponse` fields are
                    `person_name`/`is_independent`/`is_chair`/`tenure_years`
                    — there's no `role` string, so it's derived from
                    `is_chair` instead of reading a nonexistent property. */}
                {boardData.map((d) => (
                  <tr key={d.person_name} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, fontSize: 'var(--text-sm)' }}>{d.person_name}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.is_chair ? 'Chair' : 'Director'}</td>
                    <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.is_independent ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                      {d.is_independent ? 'Yes' : 'No'}
                    </td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.tenure_years != null ? `${d.tenure_years}y` : '—'}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-xs)' }}>{(d.committees ?? []).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Compensation */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Executive Compensation</h2>
          {compData.length === 0 ? (
            <EmptyTable message="No compensation data available" />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Name', 'Title', 'Base', 'Stock', 'Total'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Name' || h === 'Title' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* [P1-FP-016 fix] `ExecutiveCompensationResponse` uses
                    `person_name`/`role`/`base_salary`/`stock_awards`/
                    `total_compensation`, not the camelCase names this
                    previously assumed. */}
                {compData.map((c) => (
                  <tr key={c.person_name} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, fontSize: 'var(--text-sm)' }}>{c.person_name}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.role}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.base_salary != null ? `$${(c.base_salary / 1e6).toFixed(1)}M` : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.stock_awards != null ? `$${(c.stock_awards / 1e6).toFixed(1)}M` : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>{c.total_compensation != null ? `$${(c.total_compensation / 1e6).toFixed(1)}M` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Shareholder Proposals */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Shareholder Proposals (Last Proxy)</h2>
        {proposalData.length === 0 ? (
          <EmptyTable message="No shareholder proposals available" />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Proposal', 'Mgmt Rec.', 'For %', 'Result'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Proposal' || h === 'Mgmt Rec.' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* [P1-FP-016 fix] `ShareholderProposalResponse` has no
                  `proponent`/`forPct`/`result` fields — the real fields are
                  `proposal_number`/`management_recommendation`/`vote_for_pct`/
                  `passed`, so the "Proponent" column is replaced with the
                  real "Mgmt Rec." data rather than reading an absent field. */}
              {proposalData.map((p) => (
                <tr key={p.proposal_number} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.topic ?? `Proposal ${p.proposal_number}`}</td>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.management_recommendation ?? '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.vote_for_pct != null ? `${p.vote_for_pct.toFixed(1)}%` : '—'}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.passed === true ? 'var(--color-signal-positive)' : p.passed === false ? 'var(--color-signal-negative)' : 'var(--color-text-tertiary)' }}>
                    {p.passed === true ? 'Passed' : p.passed === false ? 'Failed' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
