// ---------------------------------------------------------------------------
// Credit Profile — Ratings, Bond Inventory, Debt Maturity Wall
//
// Honesty pass (DATA_WIRING_AUDIT §8.1): the previous version rendered ~10
// hardcoded Apple-shaped blocks (covenants, credit-metric KPIs, leverage/
// coverage/liquidity ratios, leverage trajectory, equity-vs-credit divergence,
// CDS spreads, default probability, spread history) — none of which has any
// backend producer — and pointed its hooks at nonexistent /v1/fi/* paths.
//
// Rebuilt to render ONLY data that has a real backend endpoint:
//   - Credit Ratings   -> GET /v1/fixed-income/ratings/entity/{id}  (fi_ratings.py)
//   - Bond Inventory   -> GET /v1/fixed-income/issuers/{id}/bonds    (fi_bonds.py)
//   - Debt Maturity    -> GET /v1/entities/{id}/debt-maturity        (debt_maturity.py)
// Each renders an honest empty state when its underlying table is unpopulated.
// The fabricated analytics blocks were removed rather than faked; a note points
// to what's still missing.
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '@/api/client';
import { useSecurityStore } from '@/stores/securityContext';
import { EmptyState } from '@/components/feedback';
import { BondInventoryTable } from '@/components/company/BondInventoryTable';
import { MaturityWallChart } from '@/components/company/MaturityWallChart';
import type { BondRecord } from '@/components/company/BondInventoryTable';
import type { MaturityBucket } from '@/components/company/MaturityWallChart';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};
const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600,
  color: 'var(--color-text-primary)', margin: '0 0 12px 0',
};
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
};
const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
};
const noteStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)',
};

// --- Backend response shapes ------------------------------------------------

interface CurrentRatingDTO {
  agency: string;
  current_rating: string;
  outlook?: string | null;
  last_action_date?: string | null;
  is_investment_grade?: boolean | null;
}
interface CorporateBondDTO {
  cusip: string;
  coupon_rate?: number | null;
  maturity_date: string;
  outstanding_amount?: number | null;
  initial_rating_sp?: string | null;
  initial_rating_moodys?: string | null;
  floating_spread_bps?: number | null;
}
interface PaginatedBonds { data: CorporateBondDTO[] }
interface MaturityBucketDTO { year: number; total_amount?: number | null }
interface DebtMaturityDTO {
  buckets: MaturityBucketDTO[];
  debt_maturing_1yr?: number | null;
  weighted_avg_maturity_years?: number | null;
}

export default function CreditProfile() {
  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const companyName = primary?.name ?? primary?.ticker ?? 'Unknown';
  const companyTicker = primary?.ticker ?? resolvedId ?? '--';
  const enabled = !!resolvedId;

  const ratingsQ = useQuery({
    queryKey: ['credit', 'ratings', resolvedId],
    queryFn: () => api.get<CurrentRatingDTO[]>(`/v1/fixed-income/ratings/entity/${resolvedId}`),
    enabled,
    retry: 0,
  });
  const bondsQ = useQuery({
    queryKey: ['credit', 'bonds', resolvedId],
    queryFn: () => api.get<PaginatedBonds>(`/v1/fixed-income/issuers/${resolvedId}/bonds`),
    enabled,
    retry: 0,
  });
  const debtQ = useQuery({
    queryKey: ['credit', 'debt-maturity', resolvedId],
    queryFn: () => api.get<DebtMaturityDTO>(`/v1/entities/${resolvedId}/debt-maturity`),
    enabled,
    retry: 0,
  });

  const ratings = Array.isArray(ratingsQ.data) ? ratingsQ.data : [];

  const bonds: BondRecord[] = (bondsQ.data?.data ?? []).map((b) => ({
    cusip: b.cusip,
    coupon: b.coupon_rate ?? 0,
    maturity: b.maturity_date,
    outstanding: b.outstanding_amount ?? 0,
    rating: b.initial_rating_sp || b.initial_rating_moodys || '—',
    // Live spread/price/YTM are analytics not carried on the bond master —
    // shown as 0 until the bond-pricing source is wired.
    spread: b.floating_spread_bps ?? 0,
    price: 0,
    ytm: 0,
  }));

  const maturityWall: MaturityBucket[] = (debtQ.data?.buckets ?? [])
    .filter((x) => x.total_amount != null)
    .map((x) => ({ year: x.year, amount: (x.total_amount ?? 0) / 1e6 }));
  const totalDebt = maturityWall.reduce((sum, b) => sum + b.amount, 0);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Credit Profile
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{companyTicker} &mdash; {companyName}</p>
      </div>

      {!enabled ? (
        <div style={panelStyle}>
          <EmptyState icon="🏦" title="No entity selected" description="Select a company to view its credit profile." />
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start', marginBottom: 'var(--panel-gap)' }}>
            {/* Credit Ratings */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Credit Ratings</h2>
              {ratingsQ.isLoading ? (
                <EmptyState icon="⏳" title="Loading…" />
              ) : ratings.length === 0 ? (
                <EmptyState icon="🔖" title="No ratings on file" description="Credit-rating ingestion has not populated this issuer." />
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Agency', 'Rating', 'Outlook', 'Last Action'].map((h) => (
                        <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ratings.map((r) => (
                      <tr key={r.agency} style={{ height: 'var(--table-row-height)' }}>
                        <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.agency}</td>
                        <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{r.current_rating}</td>
                        <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{r.outlook ?? '—'}</td>
                        <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.last_action_date ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Debt maturity summary */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Debt Maturity Summary</h2>
              {debtQ.isLoading ? (
                <EmptyState icon="⏳" title="Loading…" />
              ) : !debtQ.data ? (
                <EmptyState icon="📅" title="No debt maturity profile" description="No maturity profile has been computed for this issuer." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                    <span style={labelStyle}>Maturing within 1Y</span>
                    <span style={{ ...dataStyle, fontWeight: 600 }}>{debtQ.data.debt_maturing_1yr != null ? `$${(debtQ.data.debt_maturing_1yr / 1e9).toFixed(2)}B` : '—'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                    <span style={labelStyle}>Weighted Avg Maturity</span>
                    <span style={{ ...dataStyle, fontWeight: 600 }}>{debtQ.data.weighted_avg_maturity_years != null ? `${debtQ.data.weighted_avg_maturity_years.toFixed(1)} yrs` : '—'}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Maturity Wall Chart */}
          <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
            <h2 style={sectionTitle}>Debt Maturity Wall</h2>
            {maturityWall.length === 0 ? (
              <EmptyState icon="🧱" title="No maturity buckets" description="Debt maturity buckets are unavailable for this issuer." />
            ) : (
              <MaturityWallChart maturities={maturityWall} totalDebt={totalDebt} height={280} />
            )}
          </div>

          {/* Bond Inventory Table */}
          <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
            <h2 style={sectionTitle}>Bond Inventory</h2>
            {bondsQ.isLoading ? (
              <EmptyState icon="⏳" title="Loading…" />
            ) : bonds.length === 0 ? (
              <EmptyState icon="📄" title="No bonds on file" description="No corporate bonds have been ingested for this issuer." />
            ) : (
              <BondInventoryTable bonds={bonds} />
            )}
          </div>

          <p style={noteStyle}>
            Spread history, covenant analysis, CDS, default-probability and leverage analytics require
            data sources not yet wired to this deployment, so they are omitted rather than shown with
            placeholder values.
          </p>
        </>
      )}
    </div>
  );
}
