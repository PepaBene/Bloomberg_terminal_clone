// ---------------------------------------------------------------------------
// Alerts View — Alert Inbox with Severity Badges, Acknowledge/Dismiss
//
// Wired to GET /v3/alerts (alerts.py), which returns a BARE ARRAY of
// AlertEventResponse { id, alert_type, priority, entity_id, title, detail,
// is_acknowledged, created_at }. The previous version read `apiAlerts.stats` /
// `apiAlerts.alerts` off that array — properties that never exist on an array —
// so it silently fell back to 10 fabricated alerts even when the API call
// succeeded (DATA_WIRING_AUDIT §8.2). Stats are now derived from the real rows.
// ---------------------------------------------------------------------------
import { useState, useCallback, useEffect, useMemo } from 'react';
import { AlertInbox, AlertTimeline } from '@/components/alerts';
import type { Alert as InboxAlert, TimelineAlert } from '@/components/alerts';
import { EmptyState } from '@/components/feedback';
import { useAlerts } from '@/hooks';
import { api } from '@/api/client';
import { ALERTS } from '@/api/endpoints';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

interface AlertEventDTO {
  id: string;
  alert_type: string;
  priority: string;
  entity_id: string;
  title: string;
  detail?: Record<string, unknown> | null;
  is_acknowledged: boolean;
  created_at: string;
}

function normSeverity(priority?: string): Severity {
  const p = (priority ?? '').toUpperCase();
  if (p === 'CRITICAL' || p === 'HIGH' || p === 'MEDIUM' || p === 'LOW') return p;
  return 'MEDIUM';
}

function humanizeType(alertType?: string): string {
  if (!alertType) return 'Alert';
  return alertType
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function AlertsView() {
  const { data: apiAlerts, isLoading, isError } = useAlerts() as {
    data: AlertEventDTO[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const rows: AlertEventDTO[] = useMemo(
    () => (Array.isArray(apiAlerts) ? apiAlerts : []),
    [apiAlerts],
  );

  const computedInboxAlerts: InboxAlert[] = useMemo(
    () =>
      rows.map((a) => ({
        id: String(a.id),
        title: a.title,
        description: `${humanizeType(a.alert_type)} alert`,
        severity: normSeverity(a.priority),
        createdAt: a.created_at,
        isRead: a.is_acknowledged === true,
      })),
    [rows],
  );

  const computedTimelineAlerts: TimelineAlert[] = useMemo(
    () =>
      rows.map((a) => ({
        id: String(a.id),
        title: a.title,
        description: `${humanizeType(a.alert_type)} alert`,
        severity: normSeverity(a.priority),
        createdAt: a.created_at,
      })),
    [rows],
  );

  // Stats derived from the real rows (the backend has no stats field).
  const stats = useMemo(() => {
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const weekAgo = now.getTime() - 7 * 24 * 60 * 60 * 1000;
    let unread = 0, critical = 0, high = 0, medium = 0, today = 0, week = 0;
    for (const a of rows) {
      const sev = normSeverity(a.priority);
      if (!a.is_acknowledged) unread += 1;
      if (sev === 'CRITICAL') critical += 1;
      if (sev === 'HIGH') high += 1;
      if (sev === 'MEDIUM') medium += 1;
      const ts = new Date(a.created_at).getTime();
      if (!Number.isNaN(ts)) {
        if (ts >= startOfDay) today += 1;
        if (ts >= weekAgo) week += 1;
      }
    }
    return [
      { label: 'Unread', value: String(unread) },
      { label: 'Critical', value: String(critical) },
      { label: 'High', value: String(high) },
      { label: 'Medium', value: String(medium) },
      { label: 'Today', value: String(today) },
      { label: 'This Week', value: String(week) },
    ];
  }, [rows]);

  const [inboxState, setInboxState] = useState<InboxAlert[]>([]);

  useEffect(() => {
    setInboxState(computedInboxAlerts);
  }, [computedInboxAlerts]);

  const handleAcknowledge = useCallback(async (id: string) => {
    setInboxState((prev) => prev.map((a) => (a.id === id ? { ...a, isRead: true } : a)));
    try { await api.post(ALERTS.acknowledge(id), {}); } catch { /* optimistic */ }
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
        {stats.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: ['Critical', 'Unread'].includes(s.label) && s.value !== '0' ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div style={{ ...panelStyle }}>
          <EmptyState icon="⏳" title="Loading alerts…" />
        </div>
      ) : isError ? (
        <div style={{ ...panelStyle }}>
          <EmptyState icon="⚠️" title="Failed to load alerts" description="Please try again later." />
        </div>
      ) : rows.length === 0 ? (
        <div style={{ ...panelStyle }}>
          <EmptyState
            icon="🔔"
            title="No alerts"
            description="Fired alert events will appear here once alert rules evaluate against live data."
          />
        </div>
      ) : (
        /* AlertInbox + AlertTimeline */
        <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          <AlertInbox
            alerts={inboxState}
            onAcknowledge={handleAcknowledge}
            onDismiss={handleDismiss}
          />
          <AlertTimeline alerts={computedTimelineAlerts} entityName="All Entities" />
        </div>
      )}
    </div>
  );
}
