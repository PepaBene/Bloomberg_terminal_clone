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

// --- Intelligence Module Data ------------------------------------------------

const intelModules: IntelModule[] = [
  { name: 'Business Model', score: 85, classification: 'Strong' },
  { name: 'Capital Allocation', score: 91, classification: 'Excellent' },
  { name: 'Management Quality', score: 82, classification: 'Strong' },
  { name: 'Balance Sheet Risk', score: 78, classification: 'Moderate' },
];

// --- Mock Data ---------------------------------------------------------------

const company = { name: 'Apple Inc.', ticker: 'AAPL' };

const businessModel = [
  { segment: 'iPhone', revPct: 52.1, marginPct: 42.3, growth: 3.8 },
  { segment: 'Services', revPct: 22.8, marginPct: 71.2, growth: 14.1 },
  { segment: 'Mac', revPct: 9.7, marginPct: 31.5, growth: -1.2 },
  { segment: 'iPad', revPct: 6.8, marginPct: 35.1, growth: 5.4 },
  { segment: 'Wearables & Accessories', revPct: 8.6, marginPct: 28.7, growth: -3.5 },
];

const capitalAllocation = [
  { year: 'FY2025', capex: 11.0, rnd: 30.7, buybacks: 90.1, dividends: 15.2, debtRepay: 9.7 },
  { year: 'FY2024', capex: 10.8, rnd: 29.0, buybacks: 77.6, dividends: 15.0, debtRepay: 11.5 },
  { year: 'FY2023', capex: 10.9, rnd: 26.3, buybacks: 77.5, dividends: 14.8, debtRepay: 16.0 },
];

const managementScores = [
  { metric: 'Capital Allocation', score: 9.1, maxScore: 10 },
  { metric: 'Execution Consistency', score: 8.7, maxScore: 10 },
  { metric: 'Shareholder Alignment', score: 8.9, maxScore: 10 },
  { metric: 'Strategic Vision', score: 7.8, maxScore: 10 },
  { metric: 'Governance Quality', score: 8.2, maxScore: 10 },
];

const balanceSheetRisk = [
  { metric: 'Net Debt / EBITDA', value: '0.4x', risk: 'Low' },
  { metric: 'Interest Coverage', value: '29.3x', risk: 'Low' },
  { metric: 'Current Ratio', value: '0.99', risk: 'Medium' },
  { metric: 'Debt Maturity (wt avg)', value: '7.2 yrs', risk: 'Low' },
  { metric: 'Pension Underfunding', value: 'N/A', risk: 'Low' },
];

// --- Component ---------------------------------------------------------------

export default function CompanyIntelligence() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  // Wire hooks
  const { data: apiIntel } = useCompanyIntelligence(resolvedId);
  const { data: apiBizModel } = useBusinessModel(resolvedId);
  const { data: apiCapAlloc } = useCapitalAllocation(resolvedId);
  const { data: apiMgmt } = useManagementIntel(resolvedId);
  const { data: apiBSRisk } = useBalanceSheetRisk(resolvedId);
  const { data: apiRevDrivers } = useRevenueDrivers(resolvedId);
  const { data: apiCostStruct } = useCostStructure(resolvedId);
  const { data: apiMargins } = useMarginAnalysis(resolvedId);
  const { data: apiMoat } = useMoatAssessment(resolvedId);
  const { data: apiSWOT } = useSWOT(resolvedId);
  const { data: apiPorter } = usePorterForces(resolvedId);

  // Use API data with mock fallback
  const activeModules = (apiIntel as any)?.modules ?? intelModules;
  const activeBizModel = (apiBizModel as any[]) ?? businessModel;
  const activeCapAlloc = (apiCapAlloc as any[]) ?? capitalAllocation;
  const activeMgmtScores = (apiMgmt as any)?.scores ?? managementScores;
  const activeBSRisk = (apiBSRisk as any[]) ?? balanceSheetRisk;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Company Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name}</p>
      </div>

      {/* Intelligence Summary + Sentiment */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)', alignItems: 'start' }}>
        <CompanyIntelCard modules={activeModules} />
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Entity Sentiment</h2>
          <SentimentGauge value={0.42} momentum="IMPROVING" label={`${company.ticker} Sentiment`} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Business Model Breakdown */}
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
              {activeBizModel.map((s) => (
                <tr key={s.segment} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.segment}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.revPct.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.marginPct.toFixed(1)}%</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: s.growth >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                    {s.growth >= 0 ? '+' : ''}{s.growth.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Capital Allocation */}
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
              {activeCapAlloc.map((r) => (
                <tr key={r.year} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.year}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.capex.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.rnd.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.buybacks.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.dividends.toFixed(1)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.debtRepay.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Management Quality Scores */}
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

        {/* Balance Sheet Risk */}
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
              {activeBSRisk.map((r) => (
                <tr key={r.metric} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.metric}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.value}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: riskColor(r.risk), fontWeight: 500 }}>{r.risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Revenue Drivers, Cost Structure, Margin Analysis */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--panel-gap)', marginTop: 'var(--panel-gap)' }}>
        {/* Revenue Drivers */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Revenue Drivers</h2>
          {(() => {
            const drivers = (apiRevDrivers as any)?.drivers ?? [
              { driver: 'iPhone Upgrades', impact: 'High', trend: 'Stable', contribution: 52.1 },
              { driver: 'Services Attach Rate', impact: 'High', trend: 'Growing', contribution: 22.8 },
              { driver: 'Installed Base Growth', impact: 'Medium', trend: 'Growing', contribution: 15.4 },
              { driver: 'ASP Increases', impact: 'Medium', trend: 'Stable', contribution: 9.7 },
            ];
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {drivers.map((d: any) => (
                  <div key={d.driver} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                    <div>
                      <div style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 500 }}>{d.driver}</div>
                      <div style={{ ...labelStyle, fontSize: 'var(--text-xs)' }}>Impact: {d.impact} &middot; {d.trend}</div>
                    </div>
                    <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{d.contribution?.toFixed(1) ?? '—'}%</span>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>

        {/* Cost Structure */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Cost Structure</h2>
          {(() => {
            const costs = (apiCostStruct as any)?.items ?? [
              { category: 'COGS', pctRevenue: 57.0, trend: 'Stable' },
              { category: 'R&D', pctRevenue: 7.8, trend: 'Rising' },
              { category: 'SG&A', pctRevenue: 6.5, trend: 'Stable' },
              { category: 'D&A', pctRevenue: 2.9, trend: 'Stable' },
            ];
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {costs.map((c: any) => (
                  <div key={c.category}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={labelStyle}>{c.category}</span>
                      <span style={{ ...dataStyle, fontSize: 'var(--text-sm)', fontWeight: 600 }}>{c.pctRevenue?.toFixed(1) ?? '—'}% of Rev</span>
                    </div>
                    <div style={{ height: '4px', background: 'var(--color-surface-border)', borderRadius: '2px' }}>
                      <div style={{ height: '100%', width: `${Math.min(c.pctRevenue ?? 0, 100)}%`, background: 'var(--color-accent-secondary)', borderRadius: '2px' }} />
                    </div>
                    <div style={{ ...labelStyle, fontSize: 'var(--text-xs)', marginTop: '2px', textAlign: 'right' }}>Trend: {c.trend}</div>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>

        {/* Margin Analysis */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Margin Analysis</h2>
          {(() => {
            const margins = (apiMargins as any)?.margins ?? [
              { metric: 'Gross Margin', current: 46.6, prior: 45.9, fiveYrAvg: 43.2 },
              { metric: 'Operating Margin', current: 33.2, prior: 31.4, fiveYrAvg: 29.8 },
              { metric: 'Net Margin', current: 26.7, prior: 25.3, fiveYrAvg: 24.1 },
              { metric: 'FCF Margin', current: 27.9, prior: 26.1, fiveYrAvg: 23.7 },
            ];
            return (
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
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{m.current?.toFixed(1) ?? '—'}%</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{m.prior?.toFixed(1) ?? '—'}%</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{m.fiveYrAvg?.toFixed(1) ?? '—'}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            );
          })()}
        </div>
      </div>

      {/* Moat Assessment */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Moat Assessment</h2>
        {apiMoat ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Rating</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)' }}>{(apiMoat as any).rating ?? 'Wide'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Trend</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-signal-positive)' }}>{(apiMoat as any).trend ?? 'Stable'}</span>
            </div>
            {(apiMoat as any).sources && (
              <div style={{ marginTop: '8px' }}>
                <span style={labelStyle}>Sources of Moat:</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                  {((apiMoat as any).sources as string[]).map((s: string) => (
                    <span key={s} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: 'var(--color-surface-overlay)', color: 'var(--color-accent-primary)' }}>{s}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Rating</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-accent-primary)' }}>Wide</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
              <span style={labelStyle}>Moat Trend</span>
              <span style={{ ...dataStyle, fontWeight: 600, color: 'var(--color-signal-positive)' }}>Stable</span>
            </div>
            <div style={{ marginTop: '8px' }}>
              <span style={labelStyle}>Sources of Moat:</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                {['Brand Power', 'Ecosystem Lock-in', 'Switching Costs', 'Network Effects (Services)'].map((s) => (
                  <span key={s} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '3px 8px', borderRadius: '3px', background: 'var(--color-surface-overlay)', color: 'var(--color-accent-primary)' }}>{s}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SWOT Analysis + Porter's Five Forces */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', marginTop: 'var(--panel-gap)' }}>
        {/* SWOT */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>SWOT Analysis</h2>
          {(() => {
            const swot = (apiSWOT as any) ?? {
              strengths: ['Unmatched brand loyalty & ecosystem', 'Services revenue growing 14%+ YoY', 'Massive cash generation ($107B FCF)'],
              weaknesses: ['iPhone concentration risk (52% of revenue)', 'Limited AI/cloud presence vs peers', 'Current ratio below 1.0'],
              opportunities: ['Vision Pro / spatial computing', 'AI integration across product line', 'Healthcare & automotive adjacencies'],
              threats: ['Regulatory antitrust actions globally', 'China revenue & supply chain risk', 'Commoditization of hardware features'],
            };
            return (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                {(['strengths', 'weaknesses', 'opportunities', 'threats'] as const).map((key) => (
                  <div key={key}>
                    <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px', color: key === 'strengths' || key === 'opportunities' ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>
                      {key}
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {(swot[key] as string[]).map((item: string, i: number) => (
                        <li key={i} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>

        {/* Porter's Five Forces */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Porter's Five Forces</h2>
          {(() => {
            const forces = (apiPorter as any)?.forces ?? [
              { name: 'Threat of New Entrants', score: 2, level: 'Low' },
              { name: 'Bargaining Power of Suppliers', score: 4, level: 'Moderate' },
              { name: 'Bargaining Power of Buyers', score: 3, level: 'Moderate' },
              { name: 'Threat of Substitutes', score: 3, level: 'Moderate' },
              { name: 'Competitive Rivalry', score: 7, level: 'High' },
            ];
            return (
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
            );
          })()}
        </div>
      </div>
    </div>
  );
}
