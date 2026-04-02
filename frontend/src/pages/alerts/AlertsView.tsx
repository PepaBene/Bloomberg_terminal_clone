// ---------------------------------------------------------------------------
// Alerts View — Alert Inbox with Severity Badges, Acknowledge/Dismiss
// ---------------------------------------------------------------------------
import { useState, useCallback, useEffect, useMemo } from 'react';
import { AlertInbox, AlertTimeline } from '@/components/alerts';
import type { Alert as InboxAlert, TimelineAlert } from '@/components/alerts';
import { useAlerts, useAlertRules } from '@/hooks';
import { api } from '@/api/client';
import { ALERTS } from '@/api/endpoints';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

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

// --- Component Data ----------------------------------------------------------

const now = new Date();
const inboxAlerts: InboxAlert[] = alerts.map((a) => ({
  id: String(a.id),
  title: a.title,
  description: `${a.type} alert for ${a.entity}: ${a.title}`,
  severity: a.severity.toUpperCase() as InboxAlert['severity'],
  entityTicker: a.entity,
  createdAt: new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt(a.time.split(':')[0] ?? '0'), parseInt(a.time.split(':')[1] ?? '0')).toISOString(),
  isRead: a.status === 'Read',
}));

const timelineAlerts: TimelineAlert[] = alerts.map((a) => ({
  id: String(a.id),
  title: a.title,
  description: `${a.type} alert for ${a.entity}: ${a.title}`,
  severity: a.severity.toUpperCase() as TimelineAlert['severity'],
  createdAt: new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt(a.time.split(':')[0] ?? '0'), parseInt(a.time.split(':')[1] ?? '0')).toISOString(),
}));

export default function AlertsView() {
  const { data: apiAlerts } = useAlerts() as { data: any };
  const { data: apiRules } = useAlertRules() as { data: any };

  const activeStats = (apiAlerts as any)?.stats ?? alertStats;
  const activeAlerts = (apiAlerts as any)?.alerts ?? alerts;

  const computedInboxAlerts: InboxAlert[] = useMemo(() => activeAlerts.map((a: any) => ({
    id: String(a.id),
    title: a.title,
    description: `${a.type} alert for ${a.entity}: ${a.title}`,
    severity: (a.severity ?? 'MEDIUM').toUpperCase() as InboxAlert['severity'],
    entityTicker: a.entity,
    createdAt: a.createdAt ?? new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt((a.time ?? '00:00').split(':')[0] ?? '0'), parseInt((a.time ?? '00:00').split(':')[1] ?? '0')).toISOString(),
    isRead: a.status === 'Read' || a.isRead === true,
  })), [activeAlerts]);

  const computedTimelineAlerts: TimelineAlert[] = useMemo(() => activeAlerts.map((a: any) => ({
    id: String(a.id),
    title: a.title,
    description: `${a.type} alert for ${a.entity}: ${a.title}`,
    severity: (a.severity ?? 'MEDIUM').toUpperCase() as TimelineAlert['severity'],
    createdAt: a.createdAt ?? new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt((a.time ?? '00:00').split(':')[0] ?? '0'), parseInt((a.time ?? '00:00').split(':')[1] ?? '0')).toISOString(),
  })), [activeAlerts]);

  const [inboxState, setInboxState] = useState(inboxAlerts);

  useEffect(() => {
    setInboxState(computedInboxAlerts);
  }, [computedInboxAlerts]);

  const handleAcknowledge = useCallback(async (id: string) => {
    setInboxState((prev) => prev.map((a) => (a.id === id ? { ...a, isRead: true } : a)));
    try { await api.post(ALERTS.acknowledge(id), {}); } catch {}
  }, []);

  const handleDismiss = useCallback((id: string) => {
    setInboxState((prev) => prev.filter((a) => a.id !== id));
  }, []);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Alert Inbox</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>All alerts with severity, entity tagging, and actions</p>
      </div>

      {/* Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeStats.map((s: any) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: ['Critical', 'Unread'].includes(s.label) ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* AlertInbox + AlertTimeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <AlertInbox
          alerts={inboxState}
          onAcknowledge={handleAcknowledge}
          onDismiss={handleDismiss}
        />
        <AlertTimeline alerts={computedTimelineAlerts} entityName="All Entities" />
      </div>
    </div>
  );
}
