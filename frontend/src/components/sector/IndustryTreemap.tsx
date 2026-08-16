import { useMemo, useState } from 'react';
import * as d3 from 'd3';
import { Treemap, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import type { TreemapNode } from 'recharts/types/chart/Treemap';
import { useIndustryRankings } from '@/hooks';
import { EmptyState } from '@/components/feedback';
import { ChartTooltip } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

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

interface TreemapDatum {
  name: string;
  gicsCode: string;
  value: number;
  colorValue: number | null;
  [key: string]: unknown;
}

// Metrics usable as the treemap's color dimension — market cap is reserved
// for tile size, and company count isn't a performance signal. Matches
// GET /v3/industry/rankings' allowed_metrics (industry.py).
const COLOR_METRICS: { key: string; label: string; pct?: boolean; diverging?: boolean }[] = [
  { key: 'roic_wacc_spread', label: 'ROIC − WACC Spread', pct: true, diverging: true },
  { key: 'revenue_growth_3y_cagr', label: 'Revenue CAGR (3Y)', pct: true, diverging: true },
  { key: 'revenue_growth_5y_cagr', label: 'Revenue CAGR (5Y)', pct: true, diverging: true },
  { key: 'median_roic', label: 'Median ROIC', pct: true },
  { key: 'median_gross_margin', label: 'Median Gross Margin', pct: true },
  { key: 'median_operating_margin', label: 'Median Op. Margin', pct: true },
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

/* ------------------------------------------------------------------ */
/*  Tile + tooltip renderers                                           */
/* ------------------------------------------------------------------ */

/** Renders one treemap tile — sized by market cap, colored by the selected metric. */
function TreemapTile(props: TreemapNode & { colorFn: (v: number | null) => string; formatColor: (v: number) => string }) {
  const { x, y, width, height, name, colorValue, colorFn, formatColor } = props as unknown as TreemapNode & {
    colorValue: number | null;
    colorFn: (v: number | null) => string;
    formatColor: (v: number) => string;
  };
  if (width <= 0 || height <= 0) return null;

  const canLabel = width > 44 && height > 28;
  const canShowValue = width > 60 && height > 42;

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={Math.max(width - 2, 0)}
        height={Math.max(height - 2, 0)}
        rx={2}
        fill={colorFn(colorValue)}
        stroke="var(--color-surface-base)"
        strokeWidth={2}
      />
      {canLabel && (
        <text
          x={x + 6}
          y={y + 15}
          fontFamily="var(--font-ui)"
          fontSize={11}
          fontWeight={600}
          fill="var(--color-text-primary)"
          style={{ pointerEvents: 'none' }}
        >
          {name.length > Math.floor(width / 6.5) ? `${name.slice(0, Math.floor(width / 6.5) - 1)}…` : name}
        </text>
      )}
      {canShowValue && colorValue != null && (
        <text
          x={x + 6}
          y={y + 30}
          fontFamily="var(--font-data)"
          fontSize={11}
          fill="var(--color-text-secondary)"
          style={{ pointerEvents: 'none', fontVariantNumeric: 'tabular-nums' }}
        >
          {formatColor(colorValue)}
        </text>
      )}
    </g>
  );
}

function TreemapTooltip({
  active,
  payload,
  formatColor,
  colorLabel,
}: {
  active?: boolean;
  payload?: Array<{ payload: TreemapDatum }>;
  formatColor: (v: number) => string;
  colorLabel: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <ChartTooltip
      title={`${row.name} — ${colorLabel}`}
      value={row.colorValue != null ? formatColor(row.colorValue) : '—'}
      benchmark={{ label: 'Market cap', value: formatValue(row.value, { money: true }) }}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Component — self-contained, fetches its own data                   */
/* ------------------------------------------------------------------ */

export interface IndustryTreemapProps {
  height?: number;
  /** Show the color-metric picker chips above the map (off for compact panels) */
  showMetricPicker?: boolean;
  defaultColorMetric?: string;
}

export function IndustryTreemap({ height = 360, showMetricPicker = true, defaultColorMetric = 'roic_wacc_spread' }: IndustryTreemapProps) {
  const [colorMetric, setColorMetric] = useState(defaultColorMetric);
  const { data: capData } = useIndustryRankings('total_market_cap') as { data: RankingResponse | undefined };
  const { data: colorData } = useIndustryRankings(colorMetric) as { data: RankingResponse | undefined };

  const colorMetricMeta = COLOR_METRICS.find((m) => m.key === colorMetric) ?? COLOR_METRICS[0]!;

  // Treemap: tile size = total market cap (real GET /v3/industry/rankings
  // ?metric=total_market_cap), tile color = the selected performance metric
  // from a second call to the same real endpoint. Joined client-side by
  // gics_code; industries missing a market cap are dropped rather than
  // given a fabricated size.
  const treemapData: TreemapDatum[] = useMemo(() => {
    const colorByCode = new Map((colorData?.rankings ?? []).map((r) => [r.gics_code, r.metric_value]));
    return (capData?.rankings ?? [])
      .filter((r) => typeof r.metric_value === 'number' && r.metric_value > 0)
      .map((r) => ({
        name: r.gics_name,
        gicsCode: r.gics_code,
        value: r.metric_value as number,
        colorValue: colorByCode.get(r.gics_code) ?? null,
      }));
  }, [capData, colorData]);

  const colorFn = useMemo(() => {
    const values = treemapData.map((d) => d.colorValue).filter((v): v is number => v != null);
    if (values.length === 0) return () => 'var(--color-surface-overlay)';

    if (colorMetricMeta.diverging) {
      const extent = Math.max(...values.map((v) => Math.abs(v)), 0.0001);
      const scale = d3
        .scaleLinear<string>()
        .domain([-extent, 0, extent])
        .range(['#E05252', '#171C22', '#2DB87D'])
        .clamp(true);
      return (v: number | null) => (v == null ? 'var(--color-surface-overlay)' : scale(v));
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const scale = d3
      .scaleLinear<string>()
      .domain([min, max || 1])
      .range(['#171C22', '#3B82F6'])
      .clamp(true);
    return (v: number | null) => (v == null ? 'var(--color-surface-overlay)' : scale(v));
  }, [treemapData, colorMetricMeta.diverging]);

  const formatColorValue = (v: number) =>
    colorMetricMeta.pct ? `${(v * 100).toFixed(1)}%` : v.toLocaleString('en-US', { maximumFractionDigits: 1 });

  if (treemapData.length === 0) {
    return (
      <EmptyState
        icon="🗺️"
        title="No industry map data available"
        description="Industry profiles are computed from company fundamentals; none are available yet."
      />
    );
  }

  return (
    <div>
      {showMetricPicker && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            Sized by market cap, colored by {colorMetricMeta.label}
          </span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {COLOR_METRICS.map((m) => (
              <span
                key={m.key}
                onClick={() => setColorMetric(m.key)}
                style={{
                  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', padding: '4px 10px', borderRadius: '3px',
                  background: m.key === colorMetric ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
                  color: m.key === colorMetric ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
                  cursor: 'pointer',
                }}
              >{m.label}</span>
            ))}
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <Treemap
          data={treemapData}
          dataKey="value"
          nameKey="name"
          stroke="var(--color-surface-base)"
          isAnimationActive={false}
          content={(props) => <TreemapTile {...(props as TreemapNode)} colorFn={colorFn} formatColor={formatColorValue} />}
        >
          <RechartsTooltip content={<TreemapTooltip formatColor={formatColorValue} colorLabel={colorMetricMeta.label} />} />
        </Treemap>
      </ResponsiveContainer>

      {/* Scale legend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
        <span>{colorMetricMeta.diverging ? 'Lower' : 'Min'}</span>
        <div
          style={{
            width: 140,
            height: 8,
            borderRadius: 4,
            background: colorMetricMeta.diverging
              ? 'linear-gradient(90deg, #E05252, #171C22, #2DB87D)'
              : 'linear-gradient(90deg, #171C22, #3B82F6)',
            border: '1px solid var(--color-surface-border)',
          }}
        />
        <span>{colorMetricMeta.diverging ? 'Higher' : 'Max'}</span>
        <span style={{ color: 'var(--color-text-tertiary)', marginLeft: 8 }}>Tile size = total market cap</span>
      </div>
    </div>
  );
}

export default IndustryTreemap;
