// ---------------------------------------------------------------------------
// Commodity Dashboard
//
// Honesty pass (DATA_WIRING_AUDIT §8.3): the price chart was Math.random()
// noise, the price table's price/change/percentile columns were hardcoded mock
// (the real /v3/global/commodities list only carries metadata, so real data
// would have made those columns `undefined` and crashed .toFixed), and the
// "exposed companies" map was fully invented.
//
// Now wired to real backend endpoints:
//   - Commodity list  -> GET /v3/global/commodities            (metadata)
//   - Price history   -> GET /v3/global/commodities/{code}/history
//   - Exposed cos.    -> GET /v3/global/commodities/{code}/companies
// Each renders an honest empty state when its table is unpopulated.
// ---------------------------------------------------------------------------
import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { CommodityPriceChart } from '@/components/global';
import type { CommodityPricePoint } from '@/components/global';
import { EmptyState } from '@/components/feedback';
import { useCommodities } from '@/hooks';

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

interface CommodityProfileDTO {
  id: string;
  commodity_code: string;
  commodity_name?: string | null;
  category?: string | null;
  unit?: string | null;
}
interface CommodityPriceDTO {
  commodity_code: string;
  price_date: string;
  close_price?: number | null;
}
interface CommodityExposureDTO {
  id: string;
  entity_id: string;
  exposure_type?: string | null;
  exposure_description?: string | null;
  sensitivity_score?: number | null;
}

export default function CommodityDashboard() {
  const { data: commoditiesRaw, isLoading: loadingList } = useCommodities() as {
    data: CommodityProfileDTO[] | undefined;
    isLoading: boolean;
  };
  const commodities = useMemo(
    () => (Array.isArray(commoditiesRaw) ? commoditiesRaw : []),
    [commoditiesRaw],
  );

  const categories = useMemo(() => {
    const set = new Set<string>();
    commodities.forEach((c) => c.category && set.add(c.category));
    return Array.from(set).sort();
  }, [commodities]);

  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const effectiveCategory = activeCategory ?? categories[0] ?? null;

  const filtered = commodities.filter((c) => c.category === effectiveCategory);
  const selected = filtered[0];

  const { data: historyRaw, isLoading: loadingHistory } = useQuery({
    queryKey: ['commodity', 'history', selected?.commodity_code],
    queryFn: () => api.get<CommodityPriceDTO[]>(`/v3/global/commodities/${selected!.commodity_code}/history`, { limit: 180 }),
    enabled: !!selected,
    retry: 0,
  });
  const priceData: CommodityPricePoint[] = (historyRaw ?? [])
    .filter((p) => p.close_price != null)
    .map((p) => ({ date: p.price_date, price: p.close_price as number }));

  const { data: exposureRaw, isLoading: loadingExposure } = useQuery({
    queryKey: ['commodity', 'companies', selected?.commodity_code],
    queryFn: () => api.get<CommodityExposureDTO[]>(`/v3/global/commodities/${selected!.commodity_code}/companies`),
    enabled: !!selected,
    retry: 0,
  });
  const exposedCompanies = Array.isArray(exposureRaw) ? exposureRaw : [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Commodity Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Commodity prices, trends, and company exposure analysis</p>
      </div>

      {loadingList ? (
        <div style={panelStyle}><EmptyState icon="⏳" title="Loading commodities…" /></div>
      ) : commodities.length === 0 ? (
        <div style={panelStyle}>
          <EmptyState icon="🛢️" title="No commodity data" description="Commodity ingestion (FRED) has not populated this deployment yet." />
        </div>
      ) : (
        <>
          {/* Category Tabs */}
          {categories.length > 0 && (
            <div style={{ ...panelStyle, display: 'flex', alignItems: 'center', gap: '4px', marginBottom: 'var(--panel-gap)', padding: '4px 8px' }}>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  style={{
                    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: '6px 14px', borderRadius: '4px',
                    border: 'none', cursor: 'pointer', fontWeight: effectiveCategory === cat ? 600 : 400,
                    background: effectiveCategory === cat ? 'var(--color-surface-overlay)' : 'transparent',
                    color: effectiveCategory === cat ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)',
                  }}
                >{cat}</button>
              ))}
            </div>
          )}

          {/* Price history chart for the selected commodity */}
          {selected && (
            <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
              <h2 style={sectionTitle}>{selected.commodity_name ?? selected.commodity_code} Price History</h2>
              {loadingHistory ? (
                <EmptyState icon="⏳" title="Loading price history…" />
              ) : priceData.length === 0 ? (
                <EmptyState icon="📉" title="No price history" description="No price observations available for this commodity." />
              ) : (
                <CommodityPriceChart
                  data={priceData}
                  commodity={selected.commodity_name ?? selected.commodity_code}
                  unit={selected.unit ?? ''}
                  height={260}
                />
              )}
            </div>
          )}

          {/* 2-column layout */}
          <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
            {/* Commodity metadata table */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>{effectiveCategory ?? 'All'} Commodities</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Name', 'Code', 'Unit'].map((h) => (
                      <th key={h} style={{ ...labelStyle, textAlign: h === 'Name' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.commodity_code} style={{ height: 'var(--table-row-height)' }}>
                      <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{c.commodity_name ?? c.commodity_code}</span>
                      </td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{c.commodity_code}</td>
                      <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-tertiary)' }}>{c.unit ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Exposed Companies Panel — real /companies endpoint */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Exposed Companies</h2>
              <p style={{ ...labelStyle, marginTop: '-8px', marginBottom: '12px' }}>
                Companies with {(selected?.commodity_name ?? 'this commodity').toLowerCase()} exposure
              </p>
              {loadingExposure ? (
                <EmptyState icon="⏳" title="Loading…" />
              ) : exposedCompanies.length === 0 ? (
                <EmptyState icon="🏢" title="No exposure data" description="No company-exposure records for this commodity." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {exposedCompanies.map((co) => (
                    <div key={co.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{co.exposure_type ?? 'Exposure'}</span>
                        {co.sensitivity_score != null && (
                          <span style={{ ...dataStyle, fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>β {co.sensitivity_score.toFixed(2)}</span>
                        )}
                      </div>
                      {co.exposure_description && (
                        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                          {co.exposure_description}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
