// ---------------------------------------------------------------------------
// Thesis Builder — Investment Thesis with Key Drivers, Risks, Catalysts
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useResearchThesis } from '@/hooks';
import { api, ApiError } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
import { useLoginModalStore } from '@/stores/authStore';
import type { ThesisCatalystItem, ThesisDriverItem, ThesisRiskItem } from '@/types/research';

interface ValidateThesisResponse {
  summary?: string;
}

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };
const dataStyle: React.CSSProperties = { fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' };

const HORIZONS = ['3M', '6M', '12M', '24M', '36M+'];
const CONVICTIONS = ['VERY_LOW', 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'];

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

// ---------------------------------------------------------------------------
// Create form -- mirrors the real ThesisCreateRequest body
// (src/schemas/investment_thesis_schema.py) field-for-field: thesis_title/
// investment_horizon/conviction_level/executive_summary/key_drivers/
// primary_risks/valuation_scenarios/catalysts. key_drivers/primary_risks/
// catalysts use the documented (but backend-unenforced) `{"items": [...]}`
// convention so the generated thesis renders correctly in the tables below
// and unlocks the auto-generated slide outline server-side.
// ---------------------------------------------------------------------------

interface ThesisFormBody {
  thesis_title: string;
  investment_horizon: string;
  conviction_level: string;
  executive_summary?: string;
  key_drivers?: { items: Array<{ driver: string; current_impact?: string }> };
  primary_risks?: { items: Array<{ risk: string; severity?: string }> };
  catalysts?: { items: Array<{ description: string }> };
  valuation_scenarios?: {
    current_price: number;
    bull: { target_price: number; implied_return: number };
    base: { target_price: number; implied_return: number };
    bear: { target_price: number; implied_return: number };
  };
}

function impliedReturnPct(target: number, current: number): number {
  return current !== 0 ? Math.round(((target - current) / current) * 1000) / 10 : 0;
}

function ThesisCreateForm({ onSubmit, onCancel, submitting, error }: {
  onSubmit: (body: ThesisFormBody) => void;
  onCancel: () => void;
  submitting: boolean;
  error: string | null;
}) {
  const [title, setTitle] = useState('');
  const [horizon, setHorizon] = useState('12M');
  const [conviction, setConviction] = useState('MEDIUM');
  const [summary, setSummary] = useState('');
  const [drivers, setDrivers] = useState<string[]>(['']);
  const [risks, setRisks] = useState<string[]>(['']);
  const [catalysts, setCatalysts] = useState<string[]>(['']);
  const [currentPrice, setCurrentPrice] = useState('');
  const [bullTarget, setBullTarget] = useState('');
  const [baseTarget, setBaseTarget] = useState('');
  const [bearTarget, setBearTarget] = useState('');

  const updateRow = (setter: React.Dispatch<React.SetStateAction<string[]>>, i: number, v: string) =>
    setter((rows) => rows.map((r, idx) => (idx === i ? v : r)));
  const addRow = (setter: React.Dispatch<React.SetStateAction<string[]>>) => setter((rows) => [...rows, '']);
  const removeRow = (setter: React.Dispatch<React.SetStateAction<string[]>>, i: number) =>
    setter((rows) => rows.filter((_, idx) => idx !== i));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    const cp = parseFloat(currentPrice);
    const bt = parseFloat(bullTarget);
    const bat = parseFloat(baseTarget);
    const bet = parseFloat(bearTarget);
    const hasValuation = [cp, bt, bat, bet].every((n) => !Number.isNaN(n));

    const filledDrivers = drivers.map((d) => d.trim()).filter(Boolean);
    const filledRisks = risks.map((r) => r.trim()).filter(Boolean);
    const filledCatalysts = catalysts.map((c) => c.trim()).filter(Boolean);

    onSubmit({
      thesis_title: title.trim(),
      investment_horizon: horizon,
      conviction_level: conviction,
      executive_summary: summary.trim() || undefined,
      key_drivers: filledDrivers.length ? { items: filledDrivers.map((driver) => ({ driver })) } : undefined,
      primary_risks: filledRisks.length ? { items: filledRisks.map((risk) => ({ risk })) } : undefined,
      catalysts: filledCatalysts.length ? { items: filledCatalysts.map((description) => ({ description })) } : undefined,
      valuation_scenarios: hasValuation ? {
        current_price: cp,
        bull: { target_price: bt, implied_return: impliedReturnPct(bt, cp) },
        base: { target_price: bat, implied_return: impliedReturnPct(bat, cp) },
        bear: { target_price: bet, implied_return: impliedReturnPct(bet, cp) },
      } : undefined,
    });
  };

  const rowList = (
    label: string, rows: string[], setter: React.Dispatch<React.SetStateAction<string[]>>, placeholder: string,
  ) => (
    <div>
      <div style={labelStyle}>{label}</div>
      {rows.map((v, i) => (
        <div key={i} style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
          <input
            type="text" className="terminal-input" value={v} placeholder={placeholder}
            onChange={(e) => updateRow(setter, i, e.target.value)}
            style={{ flex: 1 }}
          />
          {rows.length > 1 && (
            <button type="button" className="btn-ghost" onClick={() => removeRow(setter, i)} style={{ padding: '0 8px' }}>&times;</button>
          )}
        </div>
      ))}
      <button type="button" className="btn-ghost" onClick={() => addRow(setter)} style={{ marginTop: '4px', fontSize: 'var(--text-xs)' }}>+ Add</button>
    </div>
  );

  return (
    <form onSubmit={handleSubmit} style={{ ...panelStyle, marginBottom: 'var(--panel-gap)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px' }}>
          <div style={labelStyle}>Thesis Title</div>
          <input type="text" className="terminal-input" value={title} onChange={(e) => setTitle(e.target.value)} required style={{ width: '100%' }} />
        </div>
        <div>
          <div style={labelStyle}>Horizon</div>
          <select className="terminal-input" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            {HORIZONS.map((h) => <option key={h} value={h}>{h}</option>)}
          </select>
        </div>
        <div>
          <div style={labelStyle}>Conviction</div>
          <select className="terminal-input" value={conviction} onChange={(e) => setConviction(e.target.value)}>
            {CONVICTIONS.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
          </select>
        </div>
      </div>

      <div>
        <div style={labelStyle}>Executive Summary</div>
        <textarea
          className="terminal-input" value={summary} onChange={(e) => setSummary(e.target.value)}
          rows={3} style={{ width: '100%', resize: 'vertical', fontFamily: 'var(--font-ui)' }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
        {rowList('Key Drivers', drivers, setDrivers, 'e.g. Cloud segment growth')}
        {rowList('Primary Risks', risks, setRisks, 'e.g. Margin compression')}
        {rowList('Catalysts', catalysts, setCatalysts, 'e.g. Q3 earnings')}
      </div>

      <div>
        <div style={labelStyle}>Valuation (optional — leave any field blank to skip)</div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Current</div>
            <input type="number" step="0.01" className="terminal-input" value={currentPrice} onChange={(e) => setCurrentPrice(e.target.value)} style={{ width: '90px' }} />
          </div>
          <div>
            <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Bull Target</div>
            <input type="number" step="0.01" className="terminal-input" value={bullTarget} onChange={(e) => setBullTarget(e.target.value)} style={{ width: '90px' }} />
          </div>
          <div>
            <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Base Target</div>
            <input type="number" step="0.01" className="terminal-input" value={baseTarget} onChange={(e) => setBaseTarget(e.target.value)} style={{ width: '90px' }} />
          </div>
          <div>
            <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Bear Target</div>
            <input type="number" step="0.01" className="terminal-input" value={bearTarget} onChange={(e) => setBearTarget(e.target.value)} style={{ width: '90px' }} />
          </div>
        </div>
      </div>

      {error && <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)' }}>{error}</div>}

      <div style={{ display: 'flex', gap: '8px' }}>
        <button type="submit" className="btn-primary" disabled={submitting || !title.trim()}>
          {submitting ? 'Generating...' : 'Generate'}
        </button>
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export default function ThesisBuilder() {
  const { entityId } = useParams<{ entityId: string }>();
  // Don't fall back to NVDA — that silently shows NVIDIA's thesis as if it
  // were the user's. Disable queries until a real entity ID is provided.
  const resolvedId = entityId;
  const { data: apiThesis, isLoading, isError, refetch } = useResearchThesis(resolvedId);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const openLoginModal = useLoginModalStore((s) => s.openLoginModal);

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

  const handleGenerate = async (body: ThesisFormBody) => {
    if (!resolvedId) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      await api.post(RESEARCH.thesis.generate(resolvedId), body);
      setShowCreateForm(false);
      await refetch();
    } catch (err) {
      if (err instanceof ApiError && err.statusCode === 401) {
        openLoginModal('Sign in to create an investment thesis.');
      } else {
        setGenerateError(err instanceof ApiError ? err.detail : 'Thesis generation failed. Please try again.');
      }
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
      if (err instanceof ApiError && err.statusCode === 401) {
        openLoginModal('Sign in to validate this thesis.');
      } else {
        console.error('Thesis validation failed:', err);
        setValidationResult('Validation failed');
      }
    }
    setValidating(false);
  };

  // Empty state: no entityId provided. Generate needs a real entity_id in
  // the URL (POST /research/thesis/{entity_id}) -- there's nothing to
  // create a thesis for without one, so no create-form here.
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
          <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: 0 }}>
            Select a security or navigate from a company page to build an investment thesis.
          </p>
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
          {!showCreateForm && (
            <button className="btn-ghost" onClick={() => setShowCreateForm(true)} style={{ marginLeft: 'auto' }}>
              New Thesis
            </button>
          )}
        </div>
        {showCreateForm ? (
          <ThesisCreateForm onSubmit={handleGenerate} onCancel={() => setShowCreateForm(false)} submitting={generating} error={generateError} />
        ) : (
          <div style={{ ...panelStyle, textAlign: 'center', padding: '48px' }}>
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
              No thesis available for {resolvedId}
            </div>
            <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', margin: 0 }}>
              Click "New Thesis" to write one.
            </p>
          </div>
        )}
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
        <button className="btn-ghost" onClick={() => setShowCreateForm((v) => !v)} style={{ marginLeft: activeTargetPrice != null ? '8px' : 'auto' }}>
          New Thesis
        </button>
        <button className="btn-primary" onClick={handleValidate} disabled={validating} style={{ marginLeft: '4px' }}>
          {validating ? 'Validating...' : 'Validate Thesis'}
        </button>
      </div>
      {showCreateForm && (
        <ThesisCreateForm onSubmit={handleGenerate} onCancel={() => setShowCreateForm(false)} submitting={generating} error={generateError} />
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
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.weight != null ? `${d.weight}%` : '—'}</td>
                    <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: d.status?.includes('Above') ? 'var(--color-signal-positive)' : d.status?.includes('Ahead') ? 'var(--color-signal-warning)' : 'var(--color-text-secondary)' }}>{d.status ?? d.current_impact ?? ''}</td>
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
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.probability === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.probability ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)', color: r.impact === 'High' ? 'var(--color-signal-negative)' : 'var(--color-signal-warning)' }}>{r.impact ?? r.severity ?? '—'}</td>
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
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: c.expectedImpact === 'Positive' ? 'var(--color-signal-positive)' : 'var(--color-signal-warning)' }}>{c.expectedImpact ?? '—'}</td>
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
