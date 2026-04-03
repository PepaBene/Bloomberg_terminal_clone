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

const MOCK_BOARD: any[] = [];

const MOCK_COMPENSATION: any[] = [];

const MOCK_PROPOSALS: any[] = [];

const MOCK_OVERVIEW = {
  boardSize: 0, independentPct: 0, avgTenure: 0, genderDiversity: 0,
  ceoChairSplit: false, poisonPill: false, classifiedBoard: false,
  sayOnPayApproval: 0, annualElections: false,
};

export default function GovernanceDashboard() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const { data: apiGov } = useGovernance(resolvedId);
  const { data: apiBoard } = useGovernanceBoard(resolvedId);
  const { data: apiComp } = useGovernanceCompensation(resolvedId);
  const { data: apiProxy } = useGovernanceProxy(resolvedId);
  const { data: apiProposals } = useShareholderProposals(resolvedId);

  const overview = (apiGov as any) ?? MOCK_OVERVIEW;
  const board = (apiBoard as any[]) ?? MOCK_BOARD;
  const compensation = (apiComp as any[]) ?? MOCK_COMPENSATION;
  const proposals = (apiProposals as any[]) ?? MOCK_PROPOSALS;

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
          { label: 'Board Size', value: overview.boardSize },
          { label: 'Independent %', value: `${overview.independentPct}%` },
          { label: 'Avg Tenure', value: `${overview.avgTenure} yrs` },
          { label: 'Gender Diversity', value: `${overview.genderDiversity}%` },
          { label: 'Say-on-Pay', value: `${overview.sayOnPayApproval}%` },
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
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          {[
            { label: 'CEO/Chair Separation', value: overview.ceoChairSplit },
            { label: 'Annual Elections', value: overview.annualElections },
            { label: 'No Poison Pill', value: !overview.poisonPill },
            { label: 'No Classified Board', value: !overview.classifiedBoard },
          ].map((flag) => (
            <div key={flag.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: flag.value ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)', fontWeight: 700 }}>
                {flag.value ? '✓' : '✗'}
              </span>
              <span style={labelStyle}>{flag.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Board */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Board of Directors</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Name', 'Role', 'Independent', 'Tenure', 'Committees'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {board.map((d: any) => (
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
        </div>

        {/* Compensation */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Executive Compensation</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Name', 'Title', 'Base', 'Stock', 'Total'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Name' || h === 'Title' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {compensation.map((c: any) => (
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
        </div>
      </div>

      {/* Shareholder Proposals */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Shareholder Proposals (Last Proxy)</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Proposal', 'Proponent', 'For %', 'Result'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Proposal' || h === 'Proponent' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {proposals.map((p: any) => (
              <tr key={p.id ?? p.topic} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.topic}</td>
                <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.proponent}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{p.forPct?.toFixed(1)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: p.result === 'Passed' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{p.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
