// ---------------------------------------------------------------------------
// Anomaly View — Anomaly Detection Results, Severity Distribution
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useAnomalies, useCriticalAnomalies } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';

interface AnomalyResponse {
  id: string;
  entity_id: string;
  anomaly_type: string;
  severity_score: number;
  detected_at: string | null;
  z_score: number | null;
  observed_value: number | null;
  expected_value: number | null;
  ai_narrative: string | null;
  is_acknowledged: boolean;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

// Display-only bucketing of the real severity_score (0-100) into a label —
// no fabricated data, just a presentation grouping of a real number.
function severityLabel(score: number): 'Critical' | 'High' | 'Medium' {
  if (score >= 80) return 'Critical';
  if (score >= 60) return 'High';
  return 'Medium';
}

function severityColor(s: string): string {
  if (s === 'Critical') return 'var(--color-signal-negative)';
  if (s === 'High') return 'var(--color-signal-warning)';
  return 'var(--color-signal-neutral)';
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function shortEntity(entityId: string): string {
  return entityId.slice(0, 8);
}

function anomalyDetail(a: AnomalyResponse): string {
  if (a.ai_narrative) return a.ai_narrative;
  if (a.observed_value != null && a.expected_value != null) {
    return `Observed ${a.observed_value.toFixed(2)} vs expected ${a.expected_value.toFixed(2)}`;
  }
  return a.anomaly_type;
}

export default function AnomalyView() {
  const { data: apiActive, isLoading, isError } = useAnomalies();
  // F-012: destructure isError here too (was previously ignored) so a
  // failed critical-anomalies fetch is distinguishable from "none critical".
  const { data: apiCritical, isError: isCriticalError } = useCriticalAnomalies();
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  // F-001: GET /v4/research/anomalies/active and /critical both return a
  // bare list[AnomalyResponse] — there is no {stats, anomalies} wrapper.
  // Reading .stats/.anomalies off that array was always undefined, so the
  // page silently fell back to hardcoded mock data even when the API call
  // succeeded.
  const activeAnomalies: AnomalyResponse[] = Array.isArray(apiActive) ? (apiActive as AnomalyResponse[]) : [];
  const criticalAnomalies: AnomalyResponse[] = Array.isArray(apiCritical) ? (apiCritical as AnomalyResponse[]) : [];

  const activeStats = [
    { label: 'Total Anomalies', value: String(activeAnomalies.length) },
    { label: 'Critical', value: String(activeAnomalies.filter(a => severityLabel(a.severity_score) === 'Critical').length) },
    { label: 'High', value: String(activeAnomalies.filter(a => severityLabel(a.severity_score) === 'High').length) },
    { label: 'Medium', value: String(activeAnomalies.filter(a => severityLabel(a.severity_score) === 'Medium').length) },
    { label: 'Entities Affected', value: String(new Set(activeAnomalies.map(a => a.entity_id)).size) },
    {
      label: 'Avg Z-Score',
      value: activeAnomalies.length
        ? `${(activeAnomalies.reduce((sum, a) => sum + Math.abs(a.z_score ?? 0), 0) / activeAnomalies.length).toFixed(1)}σ`
        : '—',
    },
  ];

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
      {isCriticalError && (
        <p style={{ ...labelStyle, color: 'var(--color-signal-negative)', marginBottom: 'var(--panel-gap)' }}>Failed to load critical anomalies.</p>
      )}
      {criticalAnomalies.length > 0 && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', borderLeft: '3px solid var(--color-signal-negative)' }}>
          <h2 style={sectionTitle}>Critical Anomalies</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {criticalAnomalies.map((c) => (
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div>
                  <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)', marginRight: '8px' }}>{shortEntity(c.entity_id)}</span>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{anomalyDetail(c)}</span>
                </div>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-signal-negative)' }}>{c.z_score != null ? `${Number(c.z_score).toFixed(1)}σ` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={panelStyle}>
        <h2 style={sectionTitle}>Detected Anomalies</h2>
        {activeAnomalies.length === 0 ? (
          <p style={labelStyle}>No anomalies detected.</p>
        ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Time', 'Entity', 'Type', 'Severity', 'Z-Score', 'Detail', 'Action'].map((h) => (
              <th key={h} style={{ ...labelStyle, textAlign: h === 'Detail' ? 'left' : ['Entity', 'Type'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {activeAnomalies.map((a) => {
              const severity = severityLabel(a.severity_score);
              return (
                <tr key={a.id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{formatTime(a.detected_at)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{shortEntity(a.entity_id)}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.anomaly_type}</td>
                  <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: severityColor(severity), border: `1px solid ${severityColor(severity)}`, padding: '1px 5px', borderRadius: '3px' }}>{severity}</span>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{a.z_score != null ? `${a.z_score.toFixed(1)}σ` : '—'}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{anomalyDetail(a)}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)', textAlign: 'right' }}>
                    {(a.is_acknowledged || acknowledged.has(a.id)) ? (
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>Ack'd</span>
                    ) : (
                      <button className="btn-ghost" style={{ fontSize: 'var(--text-xs)', padding: '2px 8px' }} onClick={() => handleAcknowledge(a.id)}>Ack</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
