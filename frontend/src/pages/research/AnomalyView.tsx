// ---------------------------------------------------------------------------
// Anomaly View — Anomaly Detection Results, Severity Distribution
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useAnomalies, useCriticalAnomalies } from '@/hooks';
import { api } from '@/api/client';
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

const anomalyStats = [
  { label: 'Total Anomalies (24h)', value: '23' },
  { label: 'Critical', value: '3' },
  { label: 'High', value: '8' },
  { label: 'Medium', value: '12' },
  { label: 'Entities Affected', value: '18' },
  { label: 'Avg Z-Score', value: '2.8\u03c3' },
];

const anomalies = [
  { id: 1, time: '11:15', entity: 'AAPL', type: 'Volume', severity: 'Critical', zScore: 4.2, detail: 'Volume 3.8x 20-day average in 15-minute window' },
  { id: 2, time: '10:48', entity: 'JPM', type: 'CDS Spread', severity: 'Critical', zScore: 3.8, detail: 'CDS 5Y widened 15 bps — 3.8 sigma event' },
  { id: 3, time: '10:22', entity: 'TSLA', type: 'Sentiment', severity: 'High', zScore: 3.1, detail: 'News sentiment score dropped to -0.65 from +0.12 in 2 hours' },
  { id: 4, time: '09:45', entity: 'META', type: 'Price', severity: 'High', zScore: 2.9, detail: 'Intraday drop of 2.8% with no corresponding news catalyst' },
  { id: 5, time: '09:30', entity: 'XLE', type: 'Sector Flow', severity: 'High', zScore: 2.7, detail: 'Energy sector ETF outflows $450M in single session' },
  { id: 6, time: '09:15', entity: 'UST 10Y', type: 'Yield', severity: 'Medium', zScore: 2.3, detail: 'Yield spike of 8 bps pre-market on no scheduled data' },
  { id: 7, time: '08:42', entity: 'PFE', type: 'Insider', severity: 'Critical', zScore: 4.5, detail: 'CEO purchase $2.1M — largest insider buy in 2 years' },
  { id: 8, time: '08:30', entity: 'VIX', type: 'Volatility', severity: 'High', zScore: 2.6, detail: 'VIX futures term structure inverted — backwardation signal' },
];

export default function AnomalyView() {
  const { data: apiActive } = useAnomalies() as { data: any };
  const { data: apiCritical } = useCriticalAnomalies() as { data: any };
  const [acknowledged, setAcknowledged] = useState<Set<number>>(new Set());

  const activeStats = (apiActive as any)?.stats ?? anomalyStats;
  const activeAnomalies = (apiActive as any)?.anomalies ?? anomalies;

  const handleAcknowledge = async (anomalyId: number) => {
    try {
      await api.post(RESEARCH.anomalies.acknowledge(String(anomalyId)), {});
      setAcknowledged(prev => new Set(prev).add(anomalyId));
    } catch {}
  };

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
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{a.time}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{a.entity}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.type}</td>
                <td style={{ textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', fontWeight: 600, color: severityColor(a.severity), border: `1px solid ${severityColor(a.severity)}`, padding: '1px 5px', borderRadius: '3px' }}>{a.severity}</span>
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{a.zScore.toFixed(1)}\u03c3</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{a.detail}</td>
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
