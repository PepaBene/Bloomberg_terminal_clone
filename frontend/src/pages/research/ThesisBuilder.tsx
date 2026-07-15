// ---------------------------------------------------------------------------
// Thesis Builder — Investment Thesis with Key Drivers, Risks, Catalysts
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useResearchThesis } from '@/hooks';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
import type { ThesisCatalystItem, ThesisDriverItem, ThesisRiskItem } from '@/types/research';

interface ValidateThesisResponse {
  summary?: string;
}
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

function SkeletonBlock({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: '4px',
      }}
    />
  );
}

export default function ThesisBuilder() {
  const { entityId } = useParams<{ entityId: string }>();
  // Don't fall back to NVDA — that silently shows NVIDIA's thesis as if it
  // were the user's. Disable queries until a real entity ID is provided.
  const resolvedId = entityId;
  const { data: apiThesis, isLoading, isError } = useResearchThesis(resolvedId);
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTicker, setNewTicker] = useState('');
  const [newDirection, setNewDirection] = useState('Long');
  const [newTarget, setNewTarget] = useState('');

  // ThesisResponse has no nested `.thesis` object -- the response itself
  // *is* the thesis. key_drivers/primary_risks/catalysts are `{"items":
  // [...]}` dicts (analyst free-form JSON, see @/types/research), not flat
  // `drivers`/`risks`/`catalysts` arrays.
  const thesisData = apiThesis;
  const activeThesis = thesisData;
  const activeDrivers: ThesisDriverItem[] | undefined = thesisData?.key_drivers?.items;
  const activeRisks: ThesisRiskItem[] | undefined = thesisData?.primary_risks?.items;
  const activeCatalysts: ThesisCatalystItem[] | undefined = thesisData?.catalysts?.items;
  // ThesisResponse has no ticker/direction/targetPrice/currentPrice fields --
  // price targets live in the documented (but unenforced) valuation_scenarios
  // convention: {current_price, bull/base/bear: {target_price, implied_return}}.
  const valuation = thesisData?.valuation_scenarios;
  const activeTargetPrice = valuation?.base?.target_price;
  const activeCurrentPrice = valuation?.current_price;

  // Generate still has no working backend counterpart -- see
  // RESEARCH.thesis.generate in @/api/endpoints.ts for why (a paradigm
  // mismatch: the real create endpoint requires a full analyst write-up,
  // not this quick ticker/direction/target form). Disabled rather than
  // letting it silently fail on every click.
  //
  // Validate now has a real backend endpoint
  // (POST /research/thesis/{thesis_id}/validate) -- a structural
  // completeness/freshness check, not an AI/analyst judgment of the
  // thesis's investment merit; see the endpoint's docstring.
  const GENERATE_UNAVAILABLE_REASON =
    'Thesis creation requires sign-in and a full analyst write-up (title, drivers, risks, catalysts) -- this quick ticker/direction/target form does not match the real backend request shape yet.';

  const handleGenerate = async () => {
    if (!newTicker.trim()) return;
    setGenerating(true);
    try {
      await api.post(RESEARCH.thesis.generate, { ticker: newTicker, direction: newDirection, targetPrice: parseFloat(newTarget) || undefined });
      setShowCreateForm(false);
    } catch (err) {
      console.error('Thesis generation failed:', err);
    }
    setGenerating(false);
  };

  const handleValidate = async () => {
    if (!activeThesis) return;
    setValidating(true);
    try {
      const data = await api.post<ValidateThesisResponse>(RESEARCH.thesis.validate(activeThesis.id ?? resolvedId ?? ''), {});
      setValidationResult(data?.summary ?? 'Thesis validated successfully');
    } catch (err) {
      console.error('Thesis validation failed:', err);
      setValidationResult('Validation failed');
    }
    setValidating(false);
  };

  // Empty state: no entityId provided
  if (!resolvedId) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
        </div>
        <div style={{ ...panelStyle, textAlign: 'center', padding: '48px' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '12px' }}>
            No entity selected
          </div>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: '0 0 16px 0' }}>
            Select a security or navigate from a company page to build an investment thesis.
          </p>
          <button className="btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
            Create New Thesis
          </button>
          {showCreateForm && (
            <div style={{ marginTop: '16px', display: 'flex', gap: '8px', alignItems: 'flex-end', justifyContent: 'center' }}>
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
              <button className="btn-primary" onClick={handleGenerate} disabled={generating || true} title={GENERATE_UNAVAILABLE_REASON}>
                {generating ? 'Generating...' : 'Generate (unavailable)'}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
          <SkeletonBlock width="60px" height="20px" />
          <SkeletonBlock width="120px" height="16px" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          <div style={panelStyle}>
            <SkeletonBlock width="120px" height="20px" />
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <SkeletonBlock width="100%" height="16px" />
              <SkeletonBlock width="90%" height="16px" />
              <SkeletonBlock width="80%" height="16px" />
            </div>
          </div>
          <div style={panelStyle}>
            <SkeletonBlock width="120px" height="20px" />
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <SkeletonBlock width="100%" height="16px" />
              <SkeletonBlock width="90%" height="16px" />
              <SkeletonBlock width="80%" height="16px" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
        </div>
        <div style={{ ...panelStyle, borderLeft: '3px solid var(--color-signal-negative)' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>Failed to load thesis data. Please try again later.</span>
        </div>
      </div>
    );
  }

  // No thesis data available
  if (!activeThesis) {
    return (
      <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{resolvedId}</span>
          <button className="btn-ghost" onClick={() => setShowCreateForm(!showCreateForm)} style={{ marginLeft: 'auto' }}>
            New Thesis
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
            <button className="btn-primary" onClick={handleGenerate} disabled={generating || true} title={GENERATE_UNAVAILABLE_REASON}>
              {generating ? 'Generating...' : 'Generate (unavailable)'}
            </button>
          </div>
        )}
        <div style={{ ...panelStyle, textAlign: 'center', padding: '48px' }}>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
            No thesis available for {resolvedId}
          </div>
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: 0 }}>
            Click "New Thesis" to generate one.
          </p>
        </div>
      </div>
    );
  }

  // Main thesis view
  const activeUpside = activeTargetPrice && activeCurrentPrice
    ? ((activeTargetPrice - activeCurrentPrice) / activeCurrentPrice * 100).toFixed(1)
    : '--';

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Investment Thesis</h1>
        {/* ThesisResponse has no ticker field -- resolvedId (the route's entity
            UUID) is the only identifier available; thesis_title stands in for
            a display name, and there's no `direction` (Long/Short) field. */}
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{resolvedId}</span>
        <span style={labelStyle}>{activeThesis.thesis_title ?? ''}</span>
        {activeThesis.conviction_level && (
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-signal-positive)', background: 'var(--color-surface-overlay)', padding: '2px 8px', borderRadius: '3px' }}>{activeThesis.conviction_level}</span>
        )}
        {activeTargetPrice != null && (
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-signal-positive)', fontWeight: 600 }}>Target: ${activeTargetPrice} (+{activeUpside}%)</span>
        )}
        <button className="btn-ghost" onClick={() => setShowCreateForm(!showCreateForm)} style={{ marginLeft: activeTargetPrice != null ? '8px' : 'auto' }}>
          New Thesis
        </button>
        <button className="btn-primary" onClick={handleValidate} disabled={validating} style={{ marginLeft: '4px' }}>
          {validating ? 'Validating...' : 'Validate Thesis'}
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
          <button className="btn-primary" onClick={handleGenerate} disabled={generating || true} title={GENERATE_UNAVAILABLE_REASON}>
            {generating ? 'Generating...' : 'Generate (unavailable)'}
          </button>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Key Drivers</h2>
          {activeDrivers && activeDrivers.length > 0 ? (
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
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status?.includes('Above') ? 'var(--color-signal-positive)' : d.status?.includes('Ahead') ? 'var(--color-signal-warning)' : 'var(--color-text-secondary)' }}>{d.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '16px', textAlign: 'center' }}>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>No driver data available</span>
            </div>
          )}
        </div>
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Risk Assessment</h2>
          {activeRisks && activeRisks.length > 0 ? (
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
                      {r.mitigation && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Mitigation: {r.mitigation}</div>}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.probability === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.probability}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.impact === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.impact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '16px', textAlign: 'center' }}>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>No risk data available</span>
            </div>
          )}
        </div>
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Catalyst Calendar</h2>
          {activeCatalysts && activeCatalysts.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr>
                {['Date', 'Event', 'Expected Impact', 'Notes'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Event' || h === 'Notes' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {activeCatalysts.map((c, i) => (
                  <tr key={c.event ?? `${c.description}-${i}`} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{c.date ?? c.timing ?? ''}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{c.event ?? c.description}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.expectedImpact === 'Positive' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{c.expectedImpact}</td>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{c.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '16px', textAlign: 'center' }}>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>No catalyst data available</span>
            </div>
          )}
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
