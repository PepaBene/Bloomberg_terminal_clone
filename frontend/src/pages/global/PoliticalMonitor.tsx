// ---------------------------------------------------------------------------
// Political Monitor Dashboard
// ---------------------------------------------------------------------------
import { useState } from 'react';

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

function passageProbColor(prob: number): string {
  if (prob >= 50) return 'var(--color-signal-positive)';
  if (prob >= 20) return 'var(--color-quality-2)';
  return 'var(--color-signal-negative)';
}

function severityColor(severity: string): string {
  switch (severity) {
    case 'Critical': return '#dc2626';
    case 'High':     return 'var(--color-signal-negative)';
    case 'Medium':   return 'var(--color-quality-2)';
    case 'Low':      return 'var(--color-quality-4)';
    default:         return 'var(--color-text-secondary)';
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'Committee':    return 'var(--color-quality-3)';
    case 'Floor Vote':   return 'var(--color-accent-primary)';
    case 'Conference':   return 'var(--color-quality-2)';
    case 'Signed':       return 'var(--color-signal-positive)';
    case 'Introduced':   return 'var(--color-text-tertiary)';
    default:             return 'var(--color-text-secondary)';
  }
}

// --- Mock Data ---------------------------------------------------------------

type SectionTab = 'Legislation' | 'Regulatory' | 'Sanctions' | 'Elections';

interface BillRow {
  billId: string;
  title: string;
  type: string;
  status: string;
  sponsors: string;
  passageProb: number;
  affectedSectors: string;
}

const bills: BillRow[] = [
  { billId: 'HR-4821',  title: 'Digital Asset Market Structure Act',          type: 'House Bill',   status: 'Committee',  sponsors: 'McHenry (R), Waters (D)',     passageProb: 62,  affectedSectors: 'Financials, Technology' },
  { billId: 'S-2847',   title: 'AI Safety and Innovation Act',               type: 'Senate Bill',  status: 'Floor Vote', sponsors: 'Schumer (D), Young (R)',      passageProb: 78,  affectedSectors: 'Technology, Healthcare' },
  { billId: 'HR-6124',  title: 'Clean Energy Tax Credit Extension',          type: 'House Bill',   status: 'Committee',  sponsors: 'Pallone (D)',                 passageProb: 34,  affectedSectors: 'Energy, Utilities' },
  { billId: 'S-3201',   title: 'Pharmaceutical Pricing Reform Act',          type: 'Senate Bill',  status: 'Introduced', sponsors: 'Sanders (I), Warren (D)',     passageProb: 15,  affectedSectors: 'Healthcare' },
  { billId: 'HR-5567',  title: 'Critical Minerals Supply Chain Security',    type: 'House Bill',   status: 'Conference', sponsors: 'Manchin (D), Murkowski (R)', passageProb: 54,  affectedSectors: 'Materials, Industrials' },
  { billId: 'S-1892',   title: 'Bank Capital Requirements Modernization',   type: 'Senate Bill',  status: 'Committee',  sponsors: 'Brown (D)',                   passageProb: 28,  affectedSectors: 'Financials' },
];

interface RegulatoryAction {
  agency: string;
  type: string;
  title: string;
  severity: string;
  date: string;
}

const regulatoryActions: RegulatoryAction[] = [
  { agency: 'SEC',  type: 'Final Rule',        title: 'Enhanced Climate Disclosure Requirements',         severity: 'High',     date: '2026-03-18' },
  { agency: 'FDIC', type: 'Proposed Rule',      title: 'Bank Merger Review Process Overhaul',              severity: 'Medium',   date: '2026-03-14' },
  { agency: 'FTC',  type: 'Enforcement Action', title: 'Big Tech Antitrust: Non-Compete Clause Ban',      severity: 'Critical', date: '2026-03-10' },
  { agency: 'EPA',  type: 'Final Rule',         title: 'Methane Emissions Standards for Oil & Gas',        severity: 'High',     date: '2026-03-06' },
  { agency: 'FDA',  type: 'Guidance',           title: 'AI/ML-Based Medical Device Approval Pathway',     severity: 'Low',      date: '2026-03-02' },
];

interface SanctionsSummary {
  country: string;
  programs: number;
  latestAction: string;
}

const sanctionsSummaries: SanctionsSummary[] = [
  { country: 'Russia',      programs: 14, latestAction: 'Energy sector export controls expanded (Mar 2026)' },
  { country: 'Iran',        programs: 8,  latestAction: 'JCPOA-related waivers under review (Feb 2026)' },
  { country: 'North Korea', programs: 6,  latestAction: 'Maritime enforcement strengthened (Jan 2026)' },
];

const electionEvents = [
  { country: 'Germany',       date: '2026-09-28', type: 'Federal Election',     marketImpact: 'High' },
  { country: 'Brazil',        date: '2026-10-04', type: 'Municipal Elections',   marketImpact: 'Medium' },
  { country: 'Japan',         date: '2026-07-25', type: 'Upper House Election',  marketImpact: 'Medium' },
];

const tabs: SectionTab[] = ['Legislation', 'Regulatory', 'Sanctions', 'Elections'];

// --- Component ---------------------------------------------------------------

export default function PoliticalMonitor() {
  const [activeTab, setActiveTab] = useState<SectionTab>('Legislation');

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

      {/* Legislation Tab */}
      {activeTab === 'Legislation' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Active Bills</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Bill ID', 'Title', 'Type', 'Status', 'Sponsors', 'Passage %', 'Affected Sectors'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: h === 'Passage %' ? 'right' : 'left',
                      padding: 'var(--table-cell-py) var(--table-cell-px)',
                      borderBottom: '1px solid var(--color-surface-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => (
                <tr key={b.billId} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)', fontSize: 'var(--text-sm)' }}>{b.billId}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', maxWidth: '280px' }}>{b.title}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.type}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: statusColor(b.status),
                      background: `color-mix(in srgb, ${statusColor(b.status)} 15%, transparent)`,
                      fontWeight: 600,
                    }}>
                      {b.status}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{b.sponsors}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: passageProbColor(b.passageProb), fontWeight: 600 }}>
                    {b.passageProb}%
                  </td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.affectedSectors}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Regulatory Tab */}
      {activeTab === 'Regulatory' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Regulatory Actions</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Agency', 'Type', 'Title', 'Severity', 'Date'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: 'left',
                      padding: 'var(--table-cell-py) var(--table-cell-px)',
                      borderBottom: '1px solid var(--color-surface-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {regulatoryActions.map((ra, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)', fontSize: 'var(--text-sm)' }}>{ra.agency}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.type}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.title}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
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
                  </td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{ra.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sanctions Tab */}
      {activeTab === 'Sanctions' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Active Sanctions Programs</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {sanctionsSummaries.map((s) => (
              <div key={s.country} style={{ padding: '12px', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', color: 'var(--color-text-primary)', fontWeight: 600 }}>{s.country}</span>
                  <span style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-sm)',
                    padding: '1px 8px',
                    borderRadius: '2px',
                    color: 'var(--color-signal-negative)',
                    background: 'color-mix(in srgb, var(--color-signal-negative) 15%, transparent)',
                    fontWeight: 600,
                  }}>
                    {s.programs} programs
                  </span>
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginTop: '6px' }}>
                  {s.latestAction}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Elections Tab */}
      {activeTab === 'Elections' && (
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Upcoming Elections</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Country', 'Date', 'Type', 'Market Impact'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: 'left',
                      padding: 'var(--table-cell-py) var(--table-cell-px)',
                      borderBottom: '1px solid var(--color-surface-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {electionEvents.map((e, i) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{e.country}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.date}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{e.type}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: e.marketImpact === 'High' ? 'var(--color-signal-negative)' : 'var(--color-quality-2)',
                      background: e.marketImpact === 'High'
                        ? 'color-mix(in srgb, var(--color-signal-negative) 15%, transparent)'
                        : 'color-mix(in srgb, var(--color-quality-2) 15%, transparent)',
                      fontWeight: 600,
                    }}>
                      {e.marketImpact}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
