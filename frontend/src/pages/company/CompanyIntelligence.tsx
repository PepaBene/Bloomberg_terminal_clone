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

function riskColor(level: string): string {
  if (level === 'Low') return 'var(--color-signal-positive)';
  if (level === 'Medium') return 'var(--color-signal-warning)';
  return 'var(--color-signal-negative)';
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

// --- Component ---------------------------------------------------------------

export default function CompanyIntelligence() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const companyName = primary?.name ?? primary?.ticker ?? 'Unknown';
  const companyTicker = primary?.ticker ?? resolvedId ?? '--';

  // Wire hooks — extract isLoading and isError for each
  const { data: apiIntel, isLoading: loadingIntel, isError: errorIntel } = useCompanyIntelligence(resolvedId);
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

  // Extract data from API responses (no mock fallbacks)
  const activeModules = (apiIntel as Record<string, unknown>)?.modules as IntelModule[] | undefined;
  const activeBizModel = apiBizModel as unknown[] | undefined;
  const activeCapAlloc = apiCapAlloc as unknown[] | undefined;
  const activeMgmtScores = (apiMgmt as Record<string, unknown>)?.scores as unknown[] | undefined;
  const activeBSRisk = apiBSRisk as unknown[] | undefined;
  const drivers = (apiRevDrivers as Record<string, unknown>)?.drivers as unknown[] | undefined;
  const costs = (apiCostStruct as Record<string, unknown>)?.items as unknown[] | undefined;
  const margins = (apiMargins as Record<string, unknown>)?.margins as unknown[] | undefined;
  const moat = apiMoat as Record<string, unknown> | undefined;
  const swot = apiSWOT as Record<string, unknown> | undefined;
  const forces = (apiPorter as Record<string, unknown>)?.forces as unknown[] | undefined;

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
          <SectionSkeleton title="Capital Allocation ($B)" />
          <SectionSkeleton title="Management Quality" />
          <SectionSkeleton title="Balance Sheet Risk" />
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
          {/* Business Model Breakdown */}
          {activeBizModel && activeBizModel.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Business Model Breakdown</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Segment', 'Rev %', 'Margin %', 'Growth %'].map((h) => (
                      <th key={h} style={{ ...labelStyle, textAlign: h === 'Segment' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeBizModel.map((s: any) => (
                    <tr key={s.segment} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.segment}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.revPct?.toFixed(1) ?? '--'}%</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.marginPct?.toFixed(1) ?? '--'}%</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: (s.growth ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                        {s.growth != null ? `${s.growth >= 0 ? '+' : ''}${s.growth.toFixed(1)}%` : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyPanel title="Business Model Breakdown" message="No business model data available" />
          )}

          {/* Capital Allocation */}
          {activeCapAlloc && activeCapAlloc.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Capital Allocation ($B)</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Year', 'CapEx', 'R&D', 'Buybacks', 'Dividends', 'Debt Repay'].map((h) => (
                      <th key={h} style={{ ...labelStyle, textAlign: h === 'Year' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeCapAlloc.map((r: any) => (
                    <tr key={r.year} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.year}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.capex?.toFixed(1) ?? '--'}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.rnd?.toFixed(1) ?? '--'}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.buybacks?.toFixed(1) ?? '--'}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.dividends?.toFixed(1) ?? '--'}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.debtRepay?.toFixed(1) ?? '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyPanel title="Capital Allocation ($B)" message="No capital allocation data available" />
          )}

          {/* Management Quality Scores */}
          {activeMgmtScores && activeMgmtScores.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Management Quality</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {activeMgmtScores.map((m: any) => {
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
          {activeBSRisk && activeBSRisk.length > 0 ? (
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Balance Sheet Risk</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Metric', 'Value', 'Risk'].map((h) => (
                      <th key={h} style={{ ...labelStyle, textAlign: h === 'Metric' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeBSRisk.map((r: any) => (
                    <tr key={r.metric} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.metric}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.value}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: riskColor(r.risk), fontWeight: 500 }}>{r.risk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
              {drivers.map((d: any) => (
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
              {costs.map((c: any) => (
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
                {margins.map((m: any) => (
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
              <span style={labelStyle}>Moat Rating</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)' }}>{moat.rating ?? '--'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Trend</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-signal-positive)' }}>{moat.trend ?? '--'}</span>
            </div>
            {moat.sources && Array.isArray(moat.sources) && (
              <div style={{ marginTop: '8px' }}>
                <span style={labelStyle}>Sources of Moat:</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                  {(moat.sources as string[]).map((s: string) => (
                    <span key={s} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: 'var(--color-surface-overlay)', color: 'var(--color-accent-primary)' }}>{s}</span>
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
                    {((swot[key] as string[]) ?? []).map((item: string, i: number) => (
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
              {forces.map((f: any) => (
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
