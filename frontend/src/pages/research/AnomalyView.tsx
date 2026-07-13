// ---------------------------------------------------------------------------
// Anomaly View — Anomaly Detection Results, Severity Distribution
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useAnomalies, useCriticalAnomalies } from '@/hooks';
import { api } from '@/api/client';
import type { DetectedAnomaly } from '@/types/research';
import { RESEARCH } from '@/api/endpoints';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

function severityColor(s: string): string {
  if (s === 'Critical') return 'var(--color-signal-negative)';
  if (s === 'High') return 'var(--color-signal-warning)';
  return 'var(--color-signal-neutral)';
}

type AnomalyStat = { label: string; value: string };
type AnomalyRow = DetectedAnomaly & {
  time?: string;
  entity?: string;
  type?: string;
  zScore?: number;
  detail?: string;
};
type AnomalyPayload = { stats?: AnomalyStat[]; anomalies?: AnomalyRow[] };

export default function AnomalyView() {
  const { data: apiActive, isLoading, isError } = useAnomalies();
  const { data: apiCritical, isLoading: criticalLoading, isError: criticalError } = useCriticalAnomalies();
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  const activePayload = apiActive as AnomalyPayload | undefined;
  const criticalPayload = apiCritical as AnomalyPayload | AnomalyRow[] | undefined;
  const activeStats = activePayload?.stats ?? [];
  const activeAnomalies = activePayload?.anomalies ?? [];
  const criticalAnomalies = Array.isArray(criticalPayload) ? criticalPayload : criticalPayload?.anomalies ?? [];

  const handleAcknowledge = async (anomalyId: string) => {
    try {
      await api.post(RESEARCH.anomalies.acknowledge(anomalyId), {});
      setAcknowledged(prev => new Set(prev).add(anomalyId));
    } catch (error) {
      console.error('Failed to acknowledge anomaly:', error);
    }
  };

  if (isLoading) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Anomaly Detection</h1>
      <p style={{ ...labelStyle, marginTop: '12px' }}>Loading anomaly data...</p>
    </div>
  );

  if (isError) return (
    <div style={{ padding: '16px' }}>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Anomaly Detection</h1>
      <p style={{ ...labelStyle, marginTop: '12px', color: 'var(--color-signal-negative)' }}>Failed to load anomaly data.</p>
    </div>
  );

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Anomaly Detection</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Statistical anomalies across price, volume, sentiment, credit, and fundamentals</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {activeStats.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: s.label === 'Critical' ? 'var(--color-signal-negative)' : 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>
      {/* Critical Anomalies */}
      {!criticalLoading && !criticalError && criticalAnomalies.length > 0 && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', borderLeft: '3px solid var(--color-signal-negative)' }}>
          <h2 style={sectionTitle}>Critical Anomalies</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {criticalAnomalies.map((c: AnomalyRow, i: number) => (
              <div key={c.id ?? i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div>
                  <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)', marginRight: '8px' }}>{c.entity ?? c.ticker}</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{c.detail ?? c.description ?? c.type}</span>
                </div>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-signal-negative)' }}>{c.zScore != null ? `${Number(c.zScore).toFixed(1)}\u03c3` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={panelStyle}>
        <h2 style={sectionTitle}>Detected Anomalies</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Time', 'Entity', 'Type', 'Severity', 'Z-Score', 'Detail', 'Action'].map((h) => (
              <th key={h} style={{ ...labelStyle, textAlign: h === 'Detail' ? 'left' : ['Entity', 'Type'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {activeAnomalies.map((a) => (
              <tr key={a.id} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{a.time ?? a.detected_at ?? "—"}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{a.entity ?? a.entity_id}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.type ?? a.anomaly_type}</td>
                <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: severityColor(String(a.severity)), border: `1px solid ${severityColor(String(a.severity))}`, padding: '1px 5px', borderRadius: '3px' }}>{a.severity}</span>
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{a.zScore != null ? a.zScore.toFixed(1) : "—"}\u03c3</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.detail ?? a.narrative}</td>
                <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)', textAlign: 'right' }}>
                  {acknowledged.has(a.id) ? (
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>Ack'd</span>
                  ) : (
                    <button className="btn-ghost" style={{ fontSize: 'var(--text-xs)', padding: '2px 8px' }} onClick={() => handleAcknowledge(a.id)}>Ack</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
