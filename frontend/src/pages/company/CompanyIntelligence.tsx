// ---------------------------------------------------------------------------
// Company Intelligence — Business Model, Capital Allocation, Management Quality
// ---------------------------------------------------------------------------
import { CompanyIntelCard, SentimentGauge } from '@/components/intelligence';
import type { IntelModule } from '@/components/intelligence';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import {
  useCompanyIntelligence, useBusinessModel, useCapitalAllocation,
  useManagementIntel, useBalanceSheetRisk, useRevenueDrivers, useCostStructure, useMarginAnalysis,
  useMoatAssessment, useSWOT, usePorterForces,
} from '@/hooks';

function fmtNum(v: number | null | undefined, digits = 1): string {
  return v != null ? v.toFixed(digits) : '--';
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  return v != null ? `${v.toFixed(digits)}%` : '--';
}

interface MetricRow {
  label: string;
  value: string;
}

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

function qualityColor(score: number): string {
  if (score >= 8) return 'var(--color-quality-5)';
  if (score >= 6) return 'var(--color-quality-4)';
  if (score >= 4) return 'var(--color-quality-3)';
  if (score >= 2) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

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

function SectionSkeleton({ title }: { title: string }) {
  return (
    <div style={panelStyle}>
      <h2 style={sectionTitle}>{title}</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SkeletonBlock width="100%" height="16px" />
        <SkeletonBlock width="80%" height="16px" />
        <SkeletonBlock width="90%" height="16px" />
        <SkeletonBlock width="70%" height="16px" />
      </div>
    </div>
  );
}

function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <div style={panelStyle}>
      <h2 style={sectionTitle}>{title}</h2>
      <div style={{ padding: '16px', textAlign: 'center' }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>{message}</span>
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ ...panelStyle, borderLeft: '3px solid var(--color-signal-negative)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', color: 'var(--color-signal-negative)' }}>!</span>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{message}</span>
      </div>
    </div>
  );
}

function MetricList({ rows }: { rows: MetricRow[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      {rows.map((r) => (
        <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
          <span style={labelStyle}>{r.label}</span>
          <span style={{ ...dataStyle, fontWeight: 500 }}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

// --- Component ---------------------------------------------------------------

export default function CompanyIntelligence() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const companyName = primary?.name ?? primary?.ticker ?? 'Unknown';
  const companyTicker = primary?.ticker ?? resolvedId ?? '--';

  // Wire hooks — extract isLoading and isError for each. `data` from
  // useCompanyIntelligence isn't read directly (see activeModules below).
  const { isLoading: loadingIntel, isError: errorIntel } = useCompanyIntelligence(resolvedId);
  const { data: apiBizModel, isLoading: loadingBiz, isError: errorBiz } = useBusinessModel(resolvedId);
  const { data: apiCapAlloc, isLoading: loadingCap, isError: errorCap } = useCapitalAllocation(resolvedId);
  const { data: apiMgmt, isLoading: loadingMgmt, isError: errorMgmt } = useManagementIntel(resolvedId);
  const { data: apiBSRisk, isLoading: loadingBS, isError: errorBS } = useBalanceSheetRisk(resolvedId);
  const { data: apiRevDrivers, isLoading: loadingRev } = useRevenueDrivers(resolvedId);
  const { data: apiCostStruct, isLoading: loadingCost } = useCostStructure(resolvedId);
  const { data: apiMargins, isLoading: loadingMargins } = useMarginAnalysis(resolvedId);
  const { data: apiMoat, isLoading: loadingMoat } = useMoatAssessment(resolvedId);
  const { data: apiSWOT, isLoading: loadingSWOT } = useSWOT(resolvedId);
  const { data: apiPorter, isLoading: loadingPorter } = usePorterForces(resolvedId);

  const topLoading = loadingIntel || loadingBiz || loadingCap || loadingMgmt || loadingBS;
  const allError = errorIntel && errorBiz && errorCap && errorMgmt && errorBS;

  if (allError) return <ErrorBanner message="Failed to load company intelligence data. Please try again later." />;

  // Extract data from API responses (no mock fallbacks).
  //
  // CompanyIntelligenceResponse (apiIntel) bundles small per-assessment
  // summary dicts, not a generic per-module score list -- there is no real
  // `modules` field to read, so the Intelligence Summary card has nothing
  // to render from this endpoint yet.
  const activeModules: IntelModule[] | undefined = undefined;

  // BusinessModelResponse/CapitalAllocationResponse/BalanceSheetRiskResponse
  // are each a single per-entity assessment object (revenue_quality/scaling/
  // durability, working_capital/ma_discipline/buybacks/dividends, leverage/
  // liquidity), not an array of rows -- render their real sub-fields as
  // label/value metric lists instead of a fabricated per-segment/per-year/
  // per-metric-risk table.
  const activeBizModel: MetricRow[] = apiBizModel
    ? [
        { label: 'Recurring Revenue', value: fmtPct(apiBizModel.revenue_quality?.recurring_pct) },
        { label: 'Customer Concentration', value: fmtPct(apiBizModel.revenue_quality?.customer_concentration) },
        { label: 'Diversification Score', value: fmtNum(apiBizModel.revenue_quality?.diversification_score) },
        { label: 'Cyclicality Score', value: fmtNum(apiBizModel.revenue_quality?.cyclicality_score) },
        { label: 'Revenue / Employee', value: fmtNum(apiBizModel.revenue_quality?.revenue_per_employee, 0) },
        { label: 'Operating Leverage', value: fmtNum(apiBizModel.scaling?.operating_leverage) },
        { label: 'Incremental Margin', value: fmtPct(apiBizModel.scaling?.incremental_margin) },
        { label: 'SGA Scalability', value: fmtNum(apiBizModel.scaling?.sga_scalability) },
        { label: 'Moat Type', value: apiBizModel.durability?.moat_type ?? '--' },
        { label: 'Switching Cost Score', value: fmtNum(apiBizModel.durability?.switching_cost_score) },
        { label: 'Disruption Vulnerability', value: fmtNum(apiBizModel.durability?.disruption_vulnerability) },
      ].filter((r) => r.value !== '--')
    : [];

  const activeCapAlloc: MetricRow[] = apiCapAlloc
    ? [
        { label: 'Overall Score', value: fmtNum(apiCapAlloc.overall_score) },
        { label: 'FCF Conversion', value: fmtPct(apiCapAlloc.fcf_conversion) },
        { label: 'ROIC vs WACC Spread', value: fmtPct(apiCapAlloc.roic_vs_wacc?.spread) },
        { label: 'Cash Conversion Cycle', value: apiCapAlloc.working_capital?.ccc != null ? `${fmtNum(apiCapAlloc.working_capital.ccc, 0)}d` : '--' },
        { label: 'M&A Discipline', value: apiCapAlloc.ma_discipline ? `${apiCapAlloc.ma_discipline.acquisition_count} deals${apiCapAlloc.ma_discipline.serial_acquirer ? ' (serial acquirer)' : ''}` : '--' },
        { label: 'Shares Outstanding Trend', value: apiCapAlloc.buyback_effectiveness?.shares_outstanding_trend ?? '--' },
        { label: 'Buyback Yield', value: fmtPct(apiCapAlloc.buyback_effectiveness?.buyback_yield) },
        { label: 'Dividend FCF Coverage', value: fmtNum(apiCapAlloc.dividend_sustainability?.fcf_coverage) },
        { label: 'Dividend Sustainable', value: apiCapAlloc.dividend_sustainability ? (apiCapAlloc.dividend_sustainability.is_sustainable ? 'Yes' : 'No') : '--' },
      ].filter((r) => r.value !== '--')
    : [];

  const activeMgmtScores = apiMgmt
    ? ([
        { metric: 'Execution', score: apiMgmt.execution_score, maxScore: 100 },
        { metric: 'Governance', score: apiMgmt.governance_score, maxScore: 100 },
        { metric: 'Overall Quality', score: apiMgmt.overall_score, maxScore: 100 },
      ].filter((m): m is { metric: string; score: number; maxScore: number } => m.score != null))
    : undefined;

  const activeBSRisk: MetricRow[] = apiBSRisk
    ? [
        { label: 'Net Debt / EBITDA', value: apiBSRisk.leverage?.net_debt_ebitda != null ? `${fmtNum(apiBSRisk.leverage.net_debt_ebitda, 2)}x${apiBSRisk.leverage.net_debt_ebitda_trend ? ` (${apiBSRisk.leverage.net_debt_ebitda_trend})` : ''}` : '--' },
        { label: 'Interest Coverage', value: apiBSRisk.leverage?.interest_coverage != null ? `${fmtNum(apiBSRisk.leverage.interest_coverage, 2)}x${apiBSRisk.leverage.interest_coverage_trend ? ` (${apiBSRisk.leverage.interest_coverage_trend})` : ''}` : '--' },
        { label: 'Liquidity Ratio', value: fmtNum(apiBSRisk.liquidity?.liquidity_ratio, 2) },
        { label: 'Cash Burn Rate', value: fmtNum(apiBSRisk.liquidity?.cash_burn_rate, 0) },
        { label: 'Refinancing Risk Score', value: fmtNum(apiBSRisk.refinancing_risk_score) },
        { label: 'Altman Z-Score', value: fmtNum(apiBSRisk.z_score, 2) },
        { label: 'Credit Rating', value: apiBSRisk.fi_profile?.credit_rating ?? '--' },
      ].filter((r) => r.value !== '--')
    : [];

  // NOTE: revenue-drivers/cost-structure/margin-analysis/swot/porter-forces
  // have no backing route in the backend yet (see @/types/intelligence) --
  // these stay whatever shape the (currently always-erroring) hook returns.
  const drivers = apiRevDrivers?.drivers;
  const costs = apiCostStruct?.items;
  const margins = apiMargins?.margins;
  const moat = apiMoat;
  const swot = apiSWOT;
  const forces = apiPorter?.forces;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Company Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{companyTicker} &mdash; {companyName}</p>
      </div>

      {/* Intelligence Summary + Sentiment */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)', alignItems: 'start' }}>
        {loadingIntel ? (
          <SectionSkeleton title="Intelligence Summary" />
        ) : activeModules ? (
          <CompanyIntelCard modules={activeModules} />
        ) : (
          <EmptyPanel title="Intelligence Summary" message="No intelligence data available" />
        )}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Entity Sentiment</h2>
          <SentimentGauge value={0.42} momentum="IMPROVING" label={`${companyTicker} Sentiment`} />
        </div>
      </div>

      {topLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          <SectionSkeleton title="Business Model Breakdown" />
          <SectionSkeleton title="Capital Allocation" />
          <SectionSkeleton title="Management Quality" />
          <SectionSkeleton title="Balance Sheet Risk" />
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          {/* Business Model Breakdown */}
          {activeBizModel.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Business Model Breakdown</h2>
              <MetricList rows={activeBizModel} />
            </div>
          ) : (
            <EmptyPanel title="Business Model Breakdown" message="No business model data available" />
          )}

          {/* Capital Allocation */}
          {activeCapAlloc.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Capital Allocation</h2>
              <MetricList rows={activeCapAlloc} />
            </div>
          ) : (
            <EmptyPanel title="Capital Allocation" message="No capital allocation data available" />
          )}

          {/* Management Quality Scores */}
          {activeMgmtScores && activeMgmtScores.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Management Quality</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {activeMgmtScores.map((m) => {
                  const pct = (m.score / m.maxScore) * 100;
                  return (
                    <div key={m.metric}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={labelStyle}>{m.metric}</span>
                        <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600, color: qualityColor(m.score) }}>{m.score.toFixed(1)}</span>
                      </div>
                      <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: qualityColor(m.score), borderRadius: '2px' }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <EmptyPanel title="Management Quality" message={loadingMgmt ? 'Loading...' : 'No management data available'} />
          )}

          {/* Balance Sheet Risk */}
          {activeBSRisk.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Balance Sheet Risk</h2>
              <MetricList rows={activeBSRisk} />
            </div>
          ) : (
            <EmptyPanel title="Balance Sheet Risk" message={loadingBS ? 'Loading...' : 'No balance sheet data available'} />
          )}
        </div>
      )}

      {/* Revenue Drivers, Cost Structure, Margin Analysis */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--panel-gap)', marginTop: 'var(--panel-gap)' }}>
        {/* Revenue Drivers */}
        {loadingRev ? (
          <SectionSkeleton title="Revenue Drivers" />
        ) : drivers && drivers.length > 0 ? (
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Revenue Drivers</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {drivers.map((d) => (
                <div key={d.driver} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div>
                    <div style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 500 }}>{d.driver}</div>
                    <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Impact: {d.impact} &middot; {d.trend}</div>
                  </div>
                  <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{d.contribution?.toFixed(1) ?? '\u2014'}%</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyPanel title="Revenue Drivers" message="No revenue driver data available" />
        )}

        {/* Cost Structure */}
        {loadingCost ? (
          <SectionSkeleton title="Cost Structure" />
        ) : costs && costs.length > 0 ? (
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Cost Structure</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {costs.map((c) => (
                <div key={c.category}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={labelStyle}>{c.category}</span>
                    <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600 }}>{c.pctRevenue?.toFixed(1) ?? '\u2014'}% of Rev</span>
                  </div>
                  <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                    <div style={{ height: '100%', width: `${Math.min(c.pctRevenue ?? 0, 100)}%`, background: 'var(--color-accent-secondary)', borderRadius: '2px' }} />
                  </div>
                  <div style={{ ...labelStyle, fontSize: 'var(--text-xs)', marginTop: '2px', textAlign: 'right' }}>Trend: {c.trend}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyPanel title="Cost Structure" message="No cost structure data available" />
        )}

        {/* Margin Analysis */}
        {loadingMargins ? (
          <SectionSkeleton title="Margin Analysis" />
        ) : margins && margins.length > 0 ? (
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Margin Analysis</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Metric', 'Current', 'Prior', '5Y Avg'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {margins.map((m) => (
                  <tr key={m.metric} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{m.metric}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{m.current?.toFixed(1) ?? '\u2014'}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{m.prior?.toFixed(1) ?? '\u2014'}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{m.fiveYrAvg?.toFixed(1) ?? '\u2014'}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyPanel title="Margin Analysis" message="No margin data available" />
        )}
      </div>

      {/* Moat Assessment */}
      {loadingMoat ? (
        <div style={{ marginTop: 'var(--panel-gap)' }}><SectionSkeleton title="Moat Assessment" /></div>
      ) : moat ? (
        <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
          <h2 style={sectionTitle}>Moat Assessment</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Width</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)' }}>{moat.moat_width ?? '--'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Stability</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-signal-positive)' }}>{moat.moat_stability ?? '--'}</span>
            </div>
            {moat.moat_evidence?.evidence && moat.moat_evidence.evidence.length > 0 && (
              <div style={{ marginTop: '8px' }}>
                <span style={labelStyle}>Sources of Moat:</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                  {moat.moat_evidence.evidence.map((e, i) => (
                    <span key={e.source ?? i} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: 'var(--color-surface-overlay)', color: 'var(--color-accent-primary)' }}>{e.source ?? e.detail ?? '--'}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 'var(--panel-gap)' }}>
          <EmptyPanel title="Moat Assessment" message="No moat assessment data available" />
        </div>
      )}

      {/* SWOT Analysis + Porter's Five Forces */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginTop: 'var(--panel-gap)' }}>
        {/* SWOT */}
        {loadingSWOT ? (
          <SectionSkeleton title="SWOT Analysis" />
        ) : swot && (swot.strengths || swot.weaknesses || swot.opportunities || swot.threats) ? (
          <div style={panelStyle}>
            <h2 style={sectionTitle}>SWOT Analysis</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {(['strengths', 'weaknesses', 'opportunities', 'threats'] as const).map((key) => (
                <div key={key}>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px', color: key === 'strengths' || key === 'opportunities' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                    {key}
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {(swot[key] ?? []).map((item, i) => (
                      <li key={i} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyPanel title="SWOT Analysis" message="No SWOT data available" />
        )}

        {/* Porter's Five Forces */}
        {loadingPorter ? (
          <SectionSkeleton title="Porter's Five Forces" />
        ) : forces && forces.length > 0 ? (
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Porter's Five Forces</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {forces.map((f) => (
                <div key={f.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={labelStyle}>{f.name}</span>
                    <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600, color: f.score >= 7 ? 'var(--color-signal-negative)' : f.score >= 4 ? 'var(--color-signal-warning)' : 'var(--color-signal-positive)' }}>{f.level}</span>
                  </div>
                  <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                    <div style={{ height: '100%', width: `${(f.score / 10) * 100}%`, background: f.score >= 7 ? 'var(--color-signal-negative)' : f.score >= 4 ? 'var(--color-signal-warning)' : 'var(--color-signal-positive)', borderRadius: '2px' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyPanel title="Porter's Five Forces" message="No competitive forces data available" />
        )}
      </div>
    </div>
  );
}
