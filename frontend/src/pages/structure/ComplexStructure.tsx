// ---------------------------------------------------------------------------
// Complex Financial Structure Analysis
// Corporate/subsidiary org tree, multi-class equity control-wedge,
// off-balance-sheet/VIE exposure, and debt subordination waterfall for a
// single entity. Real backend: GET /v1/complex-structure/entity/{entityId}
// (src/api/routers/complex_structure.py), enriched with the entity's latest
// capital structure, most-recent EX-21 subsidiary snapshot, and disclosed
// share classes (2+ required for that section to appear).
// ---------------------------------------------------------------------------
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useEntityStructure } from '@/api/hooks/useComplexStructure';

// --- Real API/engine response shapes ----------------------------------------
// StructureReportResponse (src/schemas/complex_structure.py) declares each
// dimension as a generic `dict`; shapes below mirror the actual engine
// output (src/engines/complex_structure.py) field-for-field.

interface SubsidiaryTreeApi {
  total_subsidiaries: number;
  distinct_jurisdictions: number;
  jurisdiction_breakdown: Record<string, number>;
  offshore_count: number;
  offshore_pct: number;
  vie_count: number;
  minority_owned_count: number;
  max_depth: number;
  complexity_flag: boolean;
}

interface ShareClassRowApi {
  class_name: string;
  shares_outstanding: number;
  votes_per_share: number;
  economic_pct: number;
  voting_pct: number;
  wedge: number;
}

interface ShareClassesApi {
  is_dual_class: boolean;
  num_classes: number;
  control_wedge: number;
  max_voting_pct?: number;
  classes: ShareClassRowApi[];
  assessment: string;
}

interface OffBalanceSheetApi {
  components: Record<string, number>;
  total_off_balance_sheet: number;
  obs_to_assets_pct: number | null;
  materiality: string;
  has_vie: boolean;
}

interface DebtLayerApi {
  instrument_name: string;
  seniority_rank: number | null;
  is_secured: boolean;
  issuer_level: string | null;
  principal_amount: number;
  debt_ahead: number;
  pct_of_total: number;
}

interface DebtWaterfallApi {
  total_debt: number;
  num_tranches?: number;
  secured_pct: number;
  structural_subordination: boolean;
  layers: DebtLayerApi[];
  assessment: string;
}

interface StructureReportApi {
  subject: string | null;
  subsidiary_tree: SubsidiaryTreeApi;
  share_classes: ShareClassesApi;
  off_balance_sheet: OffBalanceSheetApi;
  debt_waterfall: DebtWaterfallApi;
  complexity_score: number;
  complexity_rating: string;
  flags: string[];
}

function formatMoney(v: number): string {
  if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function ratingBadgeClass(rating: string): string {
  switch (rating.toUpperCase()) {
    case 'SIMPLE': return 'terminal-badge terminal-badge-positive';
    case 'MODERATE': return 'terminal-badge terminal-badge-neutral';
    case 'COMPLEX': return 'terminal-badge terminal-badge-warning';
    case 'VERY_COMPLEX': return 'terminal-badge terminal-badge-negative';
    default: return 'terminal-badge terminal-badge-neutral';
  }
}

function LoadingSkeleton() {
  return (
    <div style={{ padding: '16px', height: '100%' }}>
      <div style={{ height: '28px', width: '280px', background: 'var(--color-surface-raised)', borderRadius: '4px' }} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '16px' }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="terminal-panel" style={{ height: '180px' }} />
        ))}
      </div>
    </div>
  );
}

export default function ComplexStructure() {
  const { entityId: routeEntityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = routeEntityId ?? primary?.entity_id ?? undefined;

  const { data: report, isLoading, isError } = useEntityStructure(resolvedId) as {
    data: StructureReportApi | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  if (!resolvedId) {
    return (
      <div style={{ padding: '16px' }}>
        <div className="terminal-panel" style={{ padding: '24px', textAlign: 'center' }}>
          <span className="terminal-label">Select a security to analyze its corporate structure.</span>
        </div>
      </div>
    );
  }

  if (isLoading) return <LoadingSkeleton />;

  if (isError || !report) {
    return (
      <div style={{ padding: '16px' }}>
        <div className="terminal-panel" style={{ borderLeft: '3px solid var(--color-signal-negative)' }}>
          <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>
            Failed to load complex-structure analysis{primary?.ticker ? ` for ${primary.ticker}` : ''}.
          </span>
        </div>
      </div>
    );
  }

  const tree = report.subsidiary_tree;
  const shares = report.share_classes;
  const obs = report.off_balance_sheet;
  const debt = report.debt_waterfall;
  const jurisdictionEntries = Object.entries(tree.jurisdiction_breakdown ?? {});

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '16px', flexWrap: 'wrap' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
          {report.subject ?? 'Complex Structure'}
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="terminal-hero">{report.complexity_score.toFixed(1)}</span>
          <span className={ratingBadgeClass(report.complexity_rating)}>{report.complexity_rating.replace(/_/g, ' ')}</span>
        </div>
      </div>

      {report.flags.length > 0 && (
        <div className="terminal-panel" style={{ marginBottom: 'var(--panel-gap)', borderLeft: '3px solid var(--color-signal-warning)' }}>
          <h2 className="terminal-section-title" style={{ fontSize: 'var(--text-md)' }}>Flags</h2>
          <ul style={{ margin: 0, paddingLeft: '18px' }}>
            {report.flags.map((f, i) => (
              <li key={i} className="terminal-label" style={{ color: 'var(--color-text-primary)' }}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Subsidiary Org Tree */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Subsidiary Org Tree</h2>
          {tree.total_subsidiaries === 0 ? (
            <span className="terminal-label">No subsidiary data on file for this entity (no EX-21 exhibit ingested).</span>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
                {[
                  { label: 'Subsidiaries', value: String(tree.total_subsidiaries) },
                  { label: 'Jurisdictions', value: String(tree.distinct_jurisdictions) },
                  { label: 'Offshore %', value: `${tree.offshore_pct.toFixed(1)}%` },
                  { label: 'Max Depth', value: String(tree.max_depth) },
                ].map((k) => (
                  <div key={k.label} style={{ textAlign: 'center' }}>
                    <div className="terminal-label" style={{ fontSize: 'var(--text-xs)' }}>{k.label}</div>
                    <div className="terminal-data" style={{ fontWeight: 600 }}>{k.value}</div>
                  </div>
                ))}
              </div>
              <table className="terminal-table">
                <thead><tr><th>Jurisdiction</th><th className="right">Count</th></tr></thead>
                <tbody>
                  {jurisdictionEntries.map(([jur, count]) => (
                    <tr key={jur}><td>{jur}</td><td className="right">{count}</td></tr>
                  ))}
                </tbody>
              </table>
              {(tree.vie_count > 0 || tree.minority_owned_count > 0) && (
                <p className="terminal-label" style={{ marginTop: '8px' }}>
                  {tree.vie_count} VIE{tree.vie_count === 1 ? '' : 's'} · {tree.minority_owned_count} minority-owned
                </p>
              )}
            </>
          )}
        </div>

        {/* Share Classes / Control Wedge */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Multi-Class Equity</h2>
          {shares.num_classes < 2 ? (
            <span className="terminal-label">{shares.assessment}</span>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
                {[
                  { label: 'Classes', value: String(shares.num_classes) },
                  { label: 'Control Wedge', value: `${shares.control_wedge.toFixed(1)}pp` },
                  { label: 'Dual Class', value: shares.is_dual_class ? 'Yes' : 'No' },
                ].map((k) => (
                  <div key={k.label} style={{ textAlign: 'center' }}>
                    <div className="terminal-label" style={{ fontSize: 'var(--text-xs)' }}>{k.label}</div>
                    <div className="terminal-data" style={{ fontWeight: 600 }}>{k.value}</div>
                  </div>
                ))}
              </div>
              <table className="terminal-table">
                <thead>
                  <tr><th>Class</th><th className="right">Shares O/S</th><th className="right">Economic %</th><th className="right">Voting %</th></tr>
                </thead>
                <tbody>
                  {shares.classes.map((c) => (
                    <tr key={c.class_name}>
                      <td style={{ fontWeight: 600 }}>{c.class_name}</td>
                      <td className="right">{c.shares_outstanding.toLocaleString()}</td>
                      <td className="right">{c.economic_pct.toFixed(1)}%</td>
                      <td className="right">{c.voting_pct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="terminal-label" style={{ marginTop: '8px', fontStyle: 'italic' }}>{shares.assessment}</p>
              <p className="terminal-label" style={{ marginTop: '4px', fontSize: 'var(--text-xs)' }}>
                Per-class voting multipliers have no ingested source yet — figures assume one-share-one-vote until real proxy data is wired up.
              </p>
            </>
          )}
        </div>

        {/* Off-Balance-Sheet / VIE Exposure */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Off-Balance-Sheet Exposure</h2>
          {obs.materiality === 'UNKNOWN' && obs.total_off_balance_sheet === 0 ? (
            <span className="terminal-label">No off-balance-sheet data on file — this platform has no ingested source for lease/guarantee/VIE commitments yet.</span>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span className="terminal-label">Total Exposure</span>
                <span className="terminal-data" style={{ fontWeight: 600 }}>{formatMoney(obs.total_off_balance_sheet)}</span>
              </div>
              <table className="terminal-table">
                <tbody>
                  {Object.entries(obs.components).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k.replace(/_/g, ' ')}</td>
                      <td className="right">{formatMoney(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: '8px' }}>
                <span className={ratingBadgeClass(obs.materiality === 'HIGH' ? 'VERY_COMPLEX' : obs.materiality === 'MODERATE' ? 'COMPLEX' : 'SIMPLE')}>
                  {obs.materiality} materiality
                </span>
              </div>
            </>
          )}
        </div>

        {/* Debt Subordination Waterfall */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Debt Waterfall</h2>
          {debt.layers.length === 0 ? (
            <span className="terminal-label">{debt.assessment}</span>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
                {[
                  { label: 'Total Debt', value: formatMoney(debt.total_debt) },
                  { label: 'Secured %', value: `${debt.secured_pct.toFixed(1)}%` },
                  { label: 'Structural Sub.', value: debt.structural_subordination ? 'Yes' : 'No' },
                ].map((k) => (
                  <div key={k.label} style={{ textAlign: 'center' }}>
                    <div className="terminal-label" style={{ fontSize: 'var(--text-xs)' }}>{k.label}</div>
                    <div className="terminal-data" style={{ fontWeight: 600 }}>{k.value}</div>
                  </div>
                ))}
              </div>
              <table className="terminal-table">
                <thead>
                  <tr><th>Instrument</th><th>Level</th><th className="right">Principal</th><th className="right">Ahead</th><th className="right">% of Total</th></tr>
                </thead>
                <tbody>
                  {debt.layers.map((l, i) => (
                    <tr key={`${l.instrument_name}-${i}`}>
                      <td style={{ fontWeight: 600 }}>
                        {l.instrument_name}
                        {l.is_secured && <span className="terminal-badge terminal-badge-positive" style={{ marginLeft: '6px' }}>Secured</span>}
                      </td>
                      <td className="terminal-label">{l.issuer_level ?? '—'}</td>
                      <td className="right">{formatMoney(l.principal_amount)}</td>
                      <td className="right">{formatMoney(l.debt_ahead)}</td>
                      <td className="right">{l.pct_of_total.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="terminal-label" style={{ marginTop: '8px', fontStyle: 'italic' }}>{debt.assessment}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
