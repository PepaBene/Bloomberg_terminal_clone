// ---------------------------------------------------------------------------
// Issuance Monitor — New Issue Calendar, Pipeline, Pricing vs Talk
// ---------------------------------------------------------------------------
import { NewIssueTable } from '@/components/fi';
import type { NewIssue } from '@/components/fi';

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

const weeklyStats = [
  { label: 'IG Volume (WTD)', value: '$28.5B' },
  { label: 'HY Volume (WTD)', value: '$8.2B' },
  { label: 'IG Avg NIC', value: '-2 bps' },
  { label: 'HY Avg NIC', value: '+5 bps' },
  { label: 'Deals Priced', value: '18' },
  { label: 'Pipeline', value: '6 deals' },
];

const pipeline = [
  { issuer: 'Amazon.com', rating: 'AA', estSize: '$4.0B', tenor: '7Y/12Y', talk: 'T+65/85', expected: '2026-03-28' },
  { issuer: 'Goldman Sachs', rating: 'A+', estSize: '$3.0B', tenor: '11NC10', talk: 'T+110', expected: '2026-03-28' },
  { issuer: 'Pfizer Inc', rating: 'A-', estSize: '$2.5B', tenor: '5Y/10Y', talk: 'T+70/95', expected: '2026-03-31' },
  { issuer: 'T-Mobile US', rating: 'BBB+', estSize: '$2.0B', tenor: '10Y', talk: 'T+105', expected: '2026-03-31' },
];

// --- NewIssueTable data (8 recent issues) ------------------------------------

const recentIssues: NewIssue[] = [
  { issuer: 'Microsoft Corp',    coupon: 3.750, maturity: '2031-09-01', size: '$5.0B', rating: 'AAA',  spread: 55,  initialTalk: 60, status: 'priced' },
  { issuer: 'JPMorgan Chase',    coupon: 4.875, maturity: '2031-06-15', size: '$3.5B', rating: 'A+',   spread: 95,  initialTalk: 100, status: 'priced' },
  { issuer: 'UnitedHealth',      coupon: 4.250, maturity: '2036-03-15', size: '$2.5B', rating: 'A+',   spread: 78,  initialTalk: 82, status: 'priced' },
  { issuer: 'Comcast Corp',      coupon: 5.125, maturity: '2056-03-01', size: '$2.0B', rating: 'A-',   spread: 115, initialTalk: 120, status: 'priced' },
  { issuer: 'Oracle Corp',       coupon: 4.750, maturity: '2036-03-15', size: '$4.0B', rating: 'BBB',  spread: 125, initialTalk: 135, status: 'priced' },
  { issuer: 'Amazon.com',        coupon: 4.125, maturity: '2038-03-15', size: '$4.0B', rating: 'AA',   spread: 72,  initialTalk: 78, status: 'launched' },
  { issuer: 'Goldman Sachs',     coupon: 5.250, maturity: '2036-03-15', size: '$3.0B', rating: 'A+',   spread: 110, initialTalk: 115, status: 'launched' },
  { issuer: 'Pfizer Inc',        coupon: 4.500, maturity: '2036-04-01', size: '$2.5B', rating: 'A-',   spread: 85,  initialTalk: 95, status: 'upcoming' },
];

// --- Component ---------------------------------------------------------------

export default function IssuanceMonitor() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          New Issue Monitor
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Primary market activity, pipeline, and pricing analysis</p>
      </div>

      {/* Weekly Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {weeklyStats.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
        {/* NewIssueTable replaces inline issuance table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Recent Issues</h2>
          <NewIssueTable issues={recentIssues} />
        </div>

        {/* Pipeline */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Pipeline</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Expected', 'Issuer', 'Rating', 'Est. Size', 'Tenor', 'IPT / Talk'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pipeline.map((p) => (
                <tr key={p.issuer} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{p.expected}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{p.issuer}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)' }}>{p.rating}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.estSize}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.tenor}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-warning)' }}>{p.talk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
