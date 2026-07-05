// ---------------------------------------------------------------------------
// Governance Dashboard — Board, Compensation, Proxy, Shareholder Proposals
// ---------------------------------------------------------------------------
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useGovernance, useGovernanceBoard, useGovernanceCompensation, useGovernanceProxy, useShareholderProposals } from '@/hooks';

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

  const { data: overview, isLoading: loadingGov, isError: errorGov } = useGovernance(resolvedId);
  const { data: board, isLoading: loadingBoard, isError: errorBoard } = useGovernanceBoard(resolvedId);
  const { data: compensation, isLoading: loadingComp, isError: errorComp } = useGovernanceCompensation(resolvedId);
  const { data: _proxy, isLoading: _loadingProxy } = useGovernanceProxy(resolvedId);
  const { data: proposals, isLoading: loadingProposals, isError: errorProposals } = useShareholderProposals(resolvedId);

  const isLoading = loadingGov || loadingBoard || loadingComp || loadingProposals;
  const isError = errorGov && errorBoard && errorComp && errorProposals;

  if (isLoading) return <LoadingSkeleton />;
  if (isError) return <ErrorState message="Failed to load governance data. Please try again later." />;

  const gov = (overview as Record<string, any>) ?? {};
  const boardData = (board as any[]) ?? [];
  const compData = (compensation as any[]) ?? [];
  const proposalData = (proposals as any[]) ?? [];

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Corporate Governance
        </h1>
        <p style={labelStyle}>Board composition, compensation, and shareholder rights</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {[
          { label: 'Board Size', value: gov.boardSize ?? '--' },
          { label: 'Independent %', value: gov.independentPct != null ? `${gov.independentPct}%` : '--' },
          { label: 'Avg Tenure', value: gov.avgTenure != null ? `${gov.avgTenure} yrs` : '--' },
          { label: 'Gender Diversity', value: gov.genderDiversity != null ? `${gov.genderDiversity}%` : '--' },
          { label: 'Say-on-Pay', value: gov.sayOnPayApproval != null ? `${gov.sayOnPayApproval}%` : '--' },
        ].map((kpi) => (
          <div key={kpi.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={labelStyle}>{kpi.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', marginTop: '4px' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Governance Flags */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Governance Provisions</h2>
        {overview ? (
          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
            {[
              { label: 'CEO/Chair Separation', value: gov.ceoChairSplit },
              { label: 'Annual Elections', value: gov.annualElections },
              { label: 'No Poison Pill', value: gov.poisonPill != null ? !gov.poisonPill : undefined },
              { label: 'No Classified Board', value: gov.classifiedBoard != null ? !gov.classifiedBoard : undefined },
            ].map((flag) => (
              <div key={flag.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: flag.value == null ? 'var(--color-text-tertiary)' : flag.value ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 700 }}>
                  {flag.value == null ? '--' : flag.value ? '\u2713' : '\u2717'}
                </span>
                <span style={labelStyle}>{flag.label}</span>
              </div>
            ))}
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
                {boardData.map((d: any) => (
                  <tr key={d.name} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, fontSize: 'var(--text-sm)' }}>{d.name}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.role}</td>
                    <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.independent ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                      {d.independent ? 'Yes' : 'No'}
                    </td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.tenure}y</td>
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
                {compData.map((c: any) => (
                  <tr key={c.name} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, fontSize: 'var(--text-sm)' }}>{c.name}</td>
                    <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.title}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>${(c.baseSalary / 1e6).toFixed(1)}M</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>${(c.stockAwards / 1e6).toFixed(1)}M</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>${(c.total / 1e6).toFixed(1)}M</td>
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
                {['Proposal', 'Proponent', 'For %', 'Result'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Proposal' || h === 'Proponent' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {proposalData.map((p: any) => (
                <tr key={p.id ?? p.topic} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.topic}</td>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.proponent}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.forPct?.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.result === 'Passed' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{p.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
