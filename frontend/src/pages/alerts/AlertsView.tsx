// ---------------------------------------------------------------------------
// Alerts View — Alert Inbox with Severity Badges, Acknowledge/Dismiss
// ---------------------------------------------------------------------------
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

function severityColor(s: string): string {
  if (s === 'Critical') return 'var(--color-signal-negative)';
  if (s === 'High') return 'var(--color-signal-warning)';
  if (s === 'Medium') return 'var(--color-signal-neutral)';
  return 'var(--color-text-tertiary)';
}

const alertStats = [
  { label: 'Unread', value: '12' },
  { label: 'Critical', value: '2' },
  { label: 'High', value: '4' },
  { label: 'Medium', value: '6' },
  { label: 'Today', value: '18' },
  { label: 'This Week', value: '47' },
];

const alerts = [
  { id: 1, time: '11:20', severity: 'Critical', type: 'Price', entity: 'AAPL', title: 'AAPL dropped 3.2% in 15 minutes — unusual volume detected', status: 'Unread' },
  { id: 2, time: '11:05', severity: 'Critical', type: 'Credit', entity: 'JPM', title: 'JPM CDS 5Y widened 15 bps — breached 2-sigma threshold', status: 'Unread' },
  { id: 3, time: '10:47', severity: 'High', type: 'Volatility', entity: 'VIX', title: 'VIX spiked above 22 — regime change to elevated vol', status: 'Unread' },
  { id: 4, time: '10:32', severity: 'High', type: 'Earnings', entity: 'MSFT', title: 'MSFT earnings in 2 days — implied move 4.2% vs 3.8% historical', status: 'Unread' },
  { id: 5, time: '09:48', severity: 'Medium', type: 'Macro', entity: 'UST', title: '10Y yield breached 4.35% resistance level', status: 'Read' },
  { id: 6, time: '09:15', severity: 'Medium', type: 'Filing', entity: 'TSLA', title: 'TSLA 8-K filed — vehicle recall announced', status: 'Read' },
  { id: 7, time: '08:45', severity: 'High', type: 'Flows', entity: 'META', title: 'Unusual institutional selling detected in META — $450M block', status: 'Unread' },
  { id: 8, time: '08:30', severity: 'Low', type: 'Data', entity: 'MACRO', title: 'Initial claims 225K vs 212K est — mild upside surprise', status: 'Read' },
  { id: 9, time: '08:15', severity: 'Medium', type: 'Rating', entity: 'F', title: 'Ford Motor credit outlook revised to Negative by Moody\'s', status: 'Read' },
  { id: 10, time: '07:50', severity: 'High', type: 'Insider', entity: 'PFE', title: 'PFE CEO purchased $2.1M in shares — largest insider buy in 2Y', status: 'Unread' },
];

export default function AlertsView() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Alert Inbox</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>All alerts with severity, entity tagging, and actions</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {alertStats.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: ['Critical', 'Unread'].includes(s.label) ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={panelStyle}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Time', 'Severity', 'Type', 'Entity', 'Alert', 'Status', 'Actions'].map((h) => (
              <th key={h} style={{ ...labelStyle, textAlign: h === 'Alert' ? 'left' : 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} style={{ height: 'var(--table-row-height)', background: a.status === 'Unread' ? 'var(--color-surface-overlay)' : 'transparent' }}>
                <td style={{ ...dataStyle, textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{a.time}</td>
                <td style={{ textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: severityColor(a.severity), background: 'var(--color-surface-base)', padding: '2px 6px', borderRadius: '3px', border: `1px solid ${severityColor(a.severity)}` }}>{a.severity}</span>
                </td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', textAlign: 'center', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.type}</td>
                <td style={{ ...dataStyle, textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600, fontSize: 'var(--text-sm)' }}>{a.entity}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.title}</td>
                <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)', color: a.status === 'Unread' ? 'var(--color-signal-warning)' : 'var(--color-text-tertiary)' }}>{a.status}</td>
                <td style={{ textAlign: 'center', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', cursor: 'pointer', marginRight: '8px' }}>ACK</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', cursor: 'pointer' }}>DISMISS</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
