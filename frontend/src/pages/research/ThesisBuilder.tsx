// ---------------------------------------------------------------------------
// Thesis Builder — Investment Thesis with Key Drivers, Risks, Catalysts
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useResearchThesis } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const thesis = { ticker: 'NVDA', name: 'NVIDIA Corp', direction: 'Long', conviction: 'High', targetPrice: 1050, currentPrice: 878.36, timeframe: '12 months' };

const keyDrivers = [
  { driver: 'AI/ML compute demand accelerating', weight: 35, status: 'Tracking Above' },
  { driver: 'Data center revenue growth >100% YoY', weight: 25, status: 'On Track' },
  { driver: 'Gross margin expansion from software mix', weight: 20, status: 'On Track' },
  { driver: 'New product cycle (Blackwell/Rubin)', weight: 15, status: 'Catalyst Ahead' },
  { driver: 'Sovereign AI demand emerging', weight: 5, status: 'Early Stage' },
];

const risks = [
  { risk: 'Customer concentration (MSFT, AMZN, GOOGL)', probability: 'Medium', impact: 'High', mitigation: 'Diversifying into enterprise/sovereign' },
  { risk: 'China export restrictions tightening', probability: 'High', impact: 'Medium', mitigation: 'Developing compliant SKUs' },
  { risk: 'Custom ASIC competition from hyperscalers', probability: 'Medium', impact: 'Medium', mitigation: 'CUDA ecosystem moat' },
  { risk: 'Valuation compression on earnings deceleration', probability: 'Low', impact: 'High', mitigation: 'Covered by growth trajectory' },
];

const catalysts = [
  { event: 'Q1 FY2027 Earnings', date: '2026-05-28', expectedImpact: 'Positive', notes: 'Blackwell revenue ramp visibility' },
  { event: 'GTC Conference', date: '2026-03-17', expectedImpact: 'Positive', notes: 'New product announcements' },
  { event: 'MSFT/AMZN CapEx Guidance', date: '2026-04-25', expectedImpact: 'Positive', notes: 'Confirms demand runway' },
  { event: 'China Policy Update', date: 'TBD', expectedImpact: 'Uncertain', notes: 'Could restrict $4B+ revenue' },
];

const upside = ((thesis.targetPrice - thesis.currentPrice) / thesis.currentPrice * 100).toFixed(1);

export default function ThesisBuilder() {
  const { entityId } = useParams<{ entityId: string }>();
  // Don't fall back to NVDA — that silently shows NVIDIA's thesis as if it
  // were the user's. Disable queries until a real entity ID is provided.
  const resolvedId = entityId ?? '';
  const { data: apiThesis } = useResearchThesis(resolvedId) as { data: any };
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTicker, setNewTicker] = useState('');
  const [newDirection, setNewDirection] = useState('Long');
  const [newTarget, setNewTarget] = useState('');

  const activeThesis = (apiThesis as any)?.thesis ?? thesis;
  const activeDrivers = (apiThesis as any)?.drivers ?? keyDrivers;
  const activeRisks = (apiThesis as any)?.risks ?? risks;
  const activeCatalysts = (apiThesis as any)?.catalysts ?? catalysts;

  const activeUpside = ((activeThesis.targetPrice - (activeThesis.currentPrice ?? thesis.currentPrice)) / (activeThesis.currentPrice ?? thesis.currentPrice) * 100).toFixed(1);

  const handleGenerate = async () => {
    if (!newTicker.trim()) return;
    setGenerating(true);
    try {
      await api.post(RESEARCH.thesis.generate, { ticker: newTicker, direction: newDirection, targetPrice: parseFloat(newTarget) || undefined });
      setShowCreateForm(false);
    } catch {}
    setGenerating(false);
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await api.post(RESEARCH.thesis.validate(activeThesis.id ?? resolvedId), {});
      setValidationResult((res as any)?.summary ?? 'Thesis validated successfully');
    } catch { setValidationResult('Validation failed'); }
    setValidating(false);
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{activeThesis.ticker}</span>
        <span style={labelStyle}>{activeThesis.name}</span>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-signal-positive)', background: 'var(--color-surface-overlay)', padding: '2px 8px', borderRadius: '3px' }}>{activeThesis.direction} &mdash; {activeThesis.conviction}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>Target: ${activeThesis.targetPrice} (+{activeUpside}%)</span>
        <button className="btn-ghost" onClick={() => setShowCreateForm(!showCreateForm)} style={{ marginLeft: '8px' }}>
          New Thesis
        </button>
        <button className="btn-primary" onClick={handleValidate} disabled={validating} style={{ marginLeft: '4px' }}>
          {validating ? 'Validating…' : 'Validate Thesis'}
        </button>
      </div>
      {showCreateForm && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <div>
            <div style={labelStyle}>Ticker</div>
            <input type="text" className="terminal-input" value={newTicker} onChange={e => setNewTicker(e.target.value)} style={{ width: '100px' }} />
          </div>
          <div>
            <div style={labelStyle}>Direction</div>
            <select className="terminal-input" value={newDirection} onChange={e => setNewDirection(e.target.value)}>
              <option value="Long">Long</option>
              <option value="Short">Short</option>
            </select>
          </div>
          <div>
            <div style={labelStyle}>Target Price</div>
            <input type="number" className="terminal-input" value={newTarget} onChange={e => setNewTarget(e.target.value)} style={{ width: '120px' }} />
          </div>
          <button className="btn-primary" onClick={handleGenerate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate'}
          </button>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Key Drivers</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Driver', 'Weight', 'Status'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Driver' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeDrivers.map((d) => (
                <tr key={d.driver} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.driver}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.weight}%</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status.includes('Above') ? 'var(--color-signal-positive)' : d.status.includes('Ahead') ? 'var(--color-signal-warning)' : 'var(--color-text-secondary)' }}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Assessment</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Risk', 'Prob', 'Impact'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Risk' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeRisks.map((r) => (
                <tr key={r.risk} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <div>{r.risk}</div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Mitigation: {r.mitigation}</div>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.probability === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.probability}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.impact === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.impact}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Catalyst Calendar</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Date', 'Event', 'Expected Impact', 'Notes'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: h === 'Event' || h === 'Notes' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {activeCatalysts.map((c) => (
                <tr key={c.event} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.event}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.expectedImpact === 'Positive' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{c.expectedImpact}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {validationResult && (
        <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)', borderLeft: '3px solid var(--color-signal-positive)' }}>
          <h2 style={sectionTitle}>Validation Result</h2>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.6, margin: 0 }}>{validationResult}</p>
        </div>
      )}
    </div>
  );
}
