// ---------------------------------------------------------------------------
// Automatic Model Builder
// Auto-assembles scored analytical models across ECONOMIC / MARKET /
// INDUSTRY / CORPORATE / COMPANY scopes. COMPANY scope auto-builds from the
// active security's real fundamentals/DCF/comps/scores on file; the other
// scopes accept caller-supplied metrics via the generic /build endpoint.
// Real backend: src/api/routers/auto_model.py (/v1/models/*).
// ---------------------------------------------------------------------------
import { useState, useMemo } from 'react';
import { useSecurityStore } from '@/stores/securityContext';
import { useModelScopes, useCompanyModel, useBuildModel } from '@/api/hooks/useAutoModel';

// --- Real API response shapes (src/schemas/auto_model.py) -------------------

interface ModelSectionApi {
  title: string;
  metrics: Record<string, unknown>;
  assessment: string;
}

interface AnalyticalModelApi {
  scope: string;
  subject: string | null;
  as_of: string | null;
  sections: ModelSectionApi[];
  drivers: string[];
  assumptions: string[];
  scores: Record<string, number>;
  composite_score: number;
  rating: string;
  summary: string;
}

interface FieldDef {
  key: string;
  label: string;
  type: 'number' | 'text';
}

const SCOPE_FIELDS: Record<string, FieldDef[]> = {
  ECONOMIC: [
    { key: 'gdp_growth', label: 'GDP Growth (% YoY)', type: 'number' },
    { key: 'inflation', label: 'Inflation (% YoY)', type: 'number' },
    { key: 'unemployment', label: 'Unemployment (%)', type: 'number' },
    { key: 'policy_rate', label: 'Policy Rate (%)', type: 'number' },
    { key: 'yield_curve_spread', label: '10y-2y Spread (%)', type: 'number' },
    { key: 'pmi', label: 'PMI', type: 'number' },
    { key: 'leading_index_change', label: 'Leading Index Chg (%)', type: 'number' },
  ],
  MARKET: [
    { key: 'index_pe', label: 'Index P/E', type: 'number' },
    { key: 'pe_percentile', label: 'P/E Percentile (0-100)', type: 'number' },
    { key: 'earnings_growth', label: 'Earnings Growth (%)', type: 'number' },
    { key: 'breadth_pct', label: 'Breadth % Above 200DMA', type: 'number' },
    { key: 'vix', label: 'VIX', type: 'number' },
    { key: 'credit_spread_bps', label: 'Credit Spread (bps)', type: 'number' },
    { key: 'trend', label: 'Trend (-1..1)', type: 'number' },
  ],
  INDUSTRY: [
    { key: 'revenue_growth', label: 'Revenue Growth (%)', type: 'number' },
    { key: 'margin_trend', label: 'Margin Trend (-1..1)', type: 'number' },
    { key: 'capex_cycle', label: 'Capex Cycle (EARLY/MID/LATE)', type: 'text' },
    { key: 'hhi', label: 'HHI (0-10000)', type: 'number' },
    { key: 'demand_score', label: 'Demand Score (0-100)', type: 'number' },
    { key: 'pricing_power', label: 'Pricing Power (-1..1)', type: 'number' },
  ],
  CORPORATE: [
    { key: 'net_debt_to_ebitda', label: 'Net Debt / EBITDA', type: 'number' },
    { key: 'interest_coverage', label: 'Interest Coverage', type: 'number' },
    { key: 'debt_to_capital', label: 'Debt / Capital (%)', type: 'number' },
    { key: 'altman_z', label: 'Altman Z-Score', type: 'number' },
    { key: 'near_term_maturities_pct', label: 'Near-Term Maturities (% ≤ 2y)', type: 'number' },
    { key: 'cash_to_debt', label: 'Cash / Debt', type: 'number' },
    { key: 'fcf_margin', label: 'FCF Margin (%)', type: 'number' },
  ],
  COMPANY: [
    { key: 'revenue_growth', label: 'Revenue Growth (%)', type: 'number' },
    { key: 'ebitda_margin', label: 'EBITDA Margin (%)', type: 'number' },
    { key: 'fcf_margin', label: 'FCF Margin (%)', type: 'number' },
    { key: 'roe', label: 'ROE (%)', type: 'number' },
    { key: 'dcf_upside_pct', label: 'DCF Upside/Downside (%)', type: 'number' },
    { key: 'pe_vs_peers', label: 'P/E vs Peers (-1..1)', type: 'number' },
    { key: 'piotroski', label: 'Piotroski F-Score (0-9)', type: 'number' },
    { key: 'altman_z', label: 'Altman Z-Score', type: 'number' },
  ],
};

function ratingBadgeClass(rating: string): string {
  const r = rating.toUpperCase();
  if (r.includes('STRONG_BUY') || r === 'EXPANSION' || r === 'STRONG') return 'terminal-badge terminal-badge-positive';
  if (r.includes('BUY')) return 'terminal-badge terminal-badge-positive';
  if (r.includes('SELL') || r === 'DISTRESSED' || r === 'CONTRACTION') return 'terminal-badge terminal-badge-negative';
  if (r === 'NEUTRAL' || r === 'ADEQUATE' || r === 'STALL' || r === 'SLOWDOWN') return 'terminal-badge terminal-badge-neutral';
  return 'terminal-badge terminal-badge-warning';
}

function ModelResult({ model }: { model: AnalyticalModelApi }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>
      <div className="terminal-panel">
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <h2 className="terminal-section-title" style={{ margin: 0 }}>{model.subject ?? model.scope}</h2>
            <p className="terminal-label" style={{ marginTop: '4px' }}>{model.as_of ? `As of ${model.as_of}` : null}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="terminal-hero">{model.composite_score.toFixed(1)}</span>
            <span className={ratingBadgeClass(model.rating)}>{model.rating.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', marginTop: '12px', lineHeight: 1.5 }}>
          {model.summary}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--panel-gap)' }}>
        {model.sections.map((s) => (
          <div key={s.title} className="terminal-panel">
            <h3 className="terminal-section-title" style={{ fontSize: 'var(--text-md)' }}>{s.title}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '10px' }}>
              {Object.entries(s.metrics).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <span className="terminal-label">{k.replace(/_/g, ' ')}</span>
                  <span className="terminal-data" style={{ fontSize: 'var(--text-sm)' }}>{v == null ? '—' : String(v)}</span>
                </div>
              ))}
            </div>
            <p className="terminal-label" style={{ fontStyle: 'italic' }}>{s.assessment}</p>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)' }}>
        <div className="terminal-panel">
          <h3 className="terminal-section-title" style={{ fontSize: 'var(--text-md)' }}>Key Drivers</h3>
          <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {model.drivers.map((d, i) => (
              <li key={i} className="terminal-label" style={{ color: 'var(--color-text-primary)' }}>{d}</li>
            ))}
          </ul>
        </div>
        <div className="terminal-panel">
          <h3 className="terminal-section-title" style={{ fontSize: 'var(--text-md)' }}>Assumptions</h3>
          <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {model.assumptions.map((a, i) => (
              <li key={i} className="terminal-label">{a}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function ModelBuilder() {
  const { data: scopesData, isLoading: scopesLoading } = useModelScopes();
  const scopes = scopesData?.scopes ?? [];

  const [selectedScope, setSelectedScope] = useState<string | null>(null);
  const activeScope = selectedScope ?? scopes[0] ?? null;

  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [subject, setSubject] = useState('');

  const primary = useSecurityStore((s) => s.primary);
  const entityId = primary?.entity_id ?? undefined;

  const {
    data: companyModel,
    isLoading: companyLoading,
    isError: companyError,
  } = useCompanyModel(entityId, { enabled: activeScope === 'COMPANY' && !!entityId }) as {
    data: AnalyticalModelApi | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const buildMutation = useBuildModel();

  const fields = useMemo(() => (activeScope ? SCOPE_FIELDS[activeScope] ?? [] : []), [activeScope]);

  const handleFieldChange = (key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleScopeChange = (scope: string) => {
    setSelectedScope(scope);
    setFormValues({});
    buildMutation.reset();
  };

  const handleBuild = () => {
    if (!activeScope) return;
    const data: Record<string, unknown> = {};
    for (const f of fields) {
      const raw = formValues[f.key];
      if (raw === undefined || raw === '') continue;
      data[f.key] = f.type === 'number' ? Number(raw) : raw;
    }
    buildMutation.mutate({ scope: activeScope, subject: subject || undefined, data });
  };

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)' }}>Automatic Model Builder</h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          Auto-assembled, scored analytical models across economic, market, industry, corporate, and company scopes
        </p>
      </div>

      {/* Scope selector */}
      <div className="terminal-panel" style={{ marginBottom: 'var(--panel-gap)' }}>
        {scopesLoading ? (
          <span className="terminal-label">Loading scopes…</span>
        ) : scopes.length === 0 ? (
          <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>Failed to load model scopes.</span>
        ) : (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {scopes.map((scope) => (
              <button
                key={scope}
                onClick={() => handleScopeChange(scope)}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  padding: '6px 16px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-surface-border)',
                  background: activeScope === scope ? 'var(--color-accent-primary)' : 'transparent',
                  color: activeScope === scope ? '#fff' : 'var(--color-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {scope}
              </button>
            ))}
          </div>
        )}
      </div>

      {activeScope === 'COMPANY' ? (
        <>
          <div className="terminal-panel" style={{ marginBottom: 'var(--panel-gap)' }}>
            <p className="terminal-label">
              Builds automatically from the active security's real fundamentals, DCF/comps valuation, and
              Piotroski/Altman scores on file.
            </p>
          </div>
          {!entityId ? (
            <div className="terminal-panel" style={{ padding: '24px', textAlign: 'center' }}>
              <span className="terminal-label">Select a security to build its company model.</span>
            </div>
          ) : companyLoading ? (
            <div className="terminal-panel" style={{ height: '160px' }} />
          ) : companyError ? (
            <div className="terminal-panel" style={{ borderLeft: '3px solid var(--color-signal-negative)' }}>
              <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>
                Failed to build a company model for {primary?.ticker ?? 'this security'}.
              </span>
            </div>
          ) : companyModel ? (
            <ModelResult model={companyModel} />
          ) : (
            <div className="terminal-panel" style={{ padding: '24px', textAlign: 'center' }}>
              <span className="terminal-label">No model data available.</span>
            </div>
          )}
        </>
      ) : activeScope ? (
        <>
          <div className="terminal-panel" style={{ marginBottom: 'var(--panel-gap)' }}>
            <h2 className="terminal-section-title" style={{ fontSize: 'var(--text-md)' }}>Inputs</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label className="terminal-label">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder={activeScope}
                  style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: '6px 8px', background: 'var(--color-surface-void)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)' }}
                />
              </div>
              {fields.map((f) => (
                <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label className="terminal-label">{f.label}</label>
                  <input
                    type={f.type === 'number' ? 'number' : 'text'}
                    value={formValues[f.key] ?? ''}
                    onChange={(e) => handleFieldChange(f.key, e.target.value)}
                    style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', padding: '6px 8px', background: 'var(--color-surface-void)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)' }}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={handleBuild}
              disabled={buildMutation.isPending}
              style={{
                marginTop: '14px',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                padding: '8px 20px',
                background: 'var(--color-accent-primary)',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: buildMutation.isPending ? 'wait' : 'pointer',
                opacity: buildMutation.isPending ? 0.6 : 1,
              }}
            >
              {buildMutation.isPending ? 'Building…' : 'Build Model'}
            </button>
          </div>

          {buildMutation.isError ? (
            <div className="terminal-panel" style={{ borderLeft: '3px solid var(--color-signal-negative)' }}>
              <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>
                {buildMutation.error instanceof Error ? buildMutation.error.message : 'Failed to build model.'}
              </span>
            </div>
          ) : buildMutation.data ? (
            <ModelResult model={buildMutation.data as AnalyticalModelApi} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
