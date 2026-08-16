// ---------------------------------------------------------------------------
// Sector / Industry View — real industry rankings by metric
//
// Honesty pass (DATA_WIRING_AUDIT §8.1/§8.2): the previous version rendered a
// fully fabricated GICS "sector performance" table (weight/1D/WTD/MTD/YTD/PE/
// relPE) plus fabricated "market breadth" KPIs — neither has any backend
// producer. `useSectors()` hit a nonexistent /v1/securities/sectors, and
// `useIndustryRankings()` read a `.breadth` field the schema never had.
//
// This page now renders the REAL, backed data: GET /v3/industry/rankings
// (industry.py) ranks industries by a selectable metric. Everything unbacked
// was removed rather than faked.
//
// The industry treemap (tile size = market cap, color = selected metric)
// lives in the reusable IndustryTreemap component (components/sector/) so
// the dashboard-builder's "Sector Heatmap" panel can drop in the same view.
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useIndustryRankings } from '@/hooks';
import { EmptyState } from '@/components/feedback';
import { IndustryTreemap } from '@/components/sector';

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

interface RankingEntry {
  gics_code: string;
  gics_name: string;
  metric_value: number | null;
  rank: number;
}
interface RankingResponse {
  metric: string;
  rankings: RankingEntry[];
}

// Metrics accepted by GET /v3/industry/rankings (industry.py allowed_metrics).
const METRICS: { key: string; label: string; pct?: boolean; money?: boolean }[] = [
  { key: 'median_roic', label: 'Median ROIC', pct: true },
  { key: 'roic_wacc_spread', label: 'ROIC − WACC Spread', pct: true },
  { key: 'median_gross_margin', label: 'Median Gross Margin', pct: true },
  { key: 'median_operating_margin', label: 'Median Op. Margin', pct: true },
  { key: 'revenue_growth_3y_cagr', label: 'Revenue CAGR (3Y)', pct: true },
  { key: 'revenue_growth_5y_cagr', label: 'Revenue CAGR (5Y)', pct: true },
  { key: 'total_market_cap', label: 'Total Market Cap', money: true },
  { key: 'company_count', label: 'Company Count' },
];

function formatValue(v: number | null, meta: { pct?: boolean; money?: boolean }): string {
  if (v == null) return '—';
  if (meta.money) {
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
    if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    return `$${v.toLocaleString('en-US')}`;
  }
  if (meta.pct) return `${(v * 100).toFixed(1)}%`;
  return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

export default function SectorView() {
  const [metric, setMetric] = useState('median_roic');
  const { data, isLoading, isError } = useIndustryRankings(metric) as {
    data: RankingResponse | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const rankings = data?.rankings ?? [];
  const metricMeta = METRICS.find((m) => m.key === metric) ?? METRICS[0]!;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Industry Rankings
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>GICS industries ranked by fundamental metric</p>
      </div>

      {/* Industry treemap — tile size = total market cap, tile color = selected metric */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Industry Map</h2>
        <IndustryTreemap height={360} />
      </div>

      {/* Metric selector */}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: 'var(--panel-gap)' }}>
        {METRICS.map((m) => (
          <span
            key={m.key}
            onClick={() => setMetric(m.key)}
            style={{
              fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '4px 10px', borderRadius: '3px',
              background: m.key === metric ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
              color: m.key === metric ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
              cursor: 'pointer',
            }}
          >{m.label}</span>
        ))}
      </div>

      <div style={panelStyle}>
        <h2 style={sectionTitle}>Ranked by {metricMeta.label}</h2>
        {isLoading ? (
          <EmptyState icon="⏳" title="Loading rankings…" />
        ) : isError ? (
          <EmptyState icon="⚠️" title="Failed to load rankings" description="Please try again later." />
        ) : rankings.length === 0 ? (
          <EmptyState
            icon="🏭"
            title="No industry data available"
            description="Industry profiles are computed from company fundamentals; none are available yet."
          />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Rank', 'GICS Code', 'Industry', metricMeta.label].map((h, i) => (
                  <th key={h} style={{ ...labelStyle, textAlign: i >= 3 ? 'right' : 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rankings.map((r) => (
                <tr key={r.gics_code} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-tertiary)' }}>{r.rank}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{r.gics_code}</td>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.gics_name}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatValue(r.metric_value, metricMeta)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
