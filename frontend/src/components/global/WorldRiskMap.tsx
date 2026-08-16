import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import * as d3 from 'd3';
import { feature } from 'topojson-client';
import type { Topology, GeometryCollection } from 'topojson-specification';
import type { FeatureCollection, Geometry } from 'geojson';
import { whereAlpha3 } from 'iso-3166-1';
import worldTopology from 'world-atlas/countries-110m.json';
import { CHART_THEME } from '../charts/chartTheme';
import { ChartTooltip } from '../charts/ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CountryRiskMapPoint {
  /** ISO 3166-1 alpha-3 code, matching the backend's country_code */
  code: string;
  name: string;
  composite: number | null;
  classification: string | null;
  trend: string | null;
}

export interface WorldRiskMapProps {
  countries: CountryRiskMapPoint[];
  height?: number;
  onSelect?: (code: string) => void;
}

interface CountryProps {
  name: string;
  [key: string]: unknown;
}

/* ------------------------------------------------------------------ */
/*  Numeric-ISO -> risk row lookup, built per-render from the same     */
/*  iso-3166-1 table the map topology's feature ids are numeric-coded  */
/*  against (world-atlas topology ids are UN M49 numeric strings).     */
/* ------------------------------------------------------------------ */

function buildLookup(countries: CountryRiskMapPoint[]): Map<string, CountryRiskMapPoint> {
  const map = new Map<string, CountryRiskMapPoint>();
  for (const c of countries) {
    const iso = whereAlpha3(c.code.toUpperCase());
    if (iso?.numeric) map.set(iso.numeric, c);
  }
  return map;
}

/* ------------------------------------------------------------------ */
/*  Color scale — sequential magnitude (risk 0-100), single hue        */
/* ------------------------------------------------------------------ */

function riskColorScale() {
  return d3
    .scaleLinear<string>()
    .domain([0, 35, 70, 100])
    .range([CHART_THEME.colors.positive, CHART_THEME.colors.highlight, CHART_THEME.colors.warning, CHART_THEME.colors.negative])
    .clamp(true);
}

const NO_DATA_FILL = '#20262d';

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function WorldRiskMap({ countries, height = 380, onSelect }: WorldRiskMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geo = useMemo(() => {
    const topo = worldTopology as unknown as Topology;
    const object = topo.objects.countries as GeometryCollection;
    return feature(topo, object) as unknown as FeatureCollection<Geometry, CountryProps>;
  }, []);

  const lookup = useMemo(() => buildLookup(countries), [countries]);
  const colorFn = useMemo(() => riskColorScale(), []);

  const projection = useMemo(() => {
    const p = d3.geoNaturalEarth1();
    p.fitSize([width, height], geo);
    return p;
  }, [width, height, geo]);

  const pathFn = useMemo(() => d3.geoPath(projection), [projection]);

  const [hovered, setHovered] = useState<{ x: number; y: number; row: CountryRiskMapPoint } | null>(null);

  const handleEnter = useCallback(
    (row: CountryRiskMapPoint | undefined, e: React.MouseEvent<SVGPathElement>) => {
      if (!row) return;
      const rect = containerRef.current?.getBoundingClientRect();
      setHovered({
        x: e.clientX - (rect?.left ?? 0),
        y: e.clientY - (rect?.top ?? 0),
        row,
      });
    },
    [],
  );

  const handleLeave = useCallback(() => setHovered(null), []);

  return (
    <div ref={containerRef} style={{ width: '100%', position: 'relative' }}>
      <svg width={width} height={height} style={{ display: 'block' }}>
        <rect x={0} y={0} width={width} height={height} fill="transparent" />
        {geo.features.map((f, i) => {
          const numericId = String((f as unknown as { id?: string | number }).id ?? '');
          const row = lookup.get(numericId);
          const d = pathFn(f);
          if (!d) return null;
          const fill = row?.composite != null ? colorFn(row.composite) : NO_DATA_FILL;

          return (
            <path
              key={i}
              d={d}
              fill={fill}
              stroke={CHART_THEME.colors.surfaceBase}
              strokeWidth={0.5}
              style={{ cursor: row ? 'pointer' : 'default', transition: 'fill 120ms ease' }}
              onMouseEnter={(e) => handleEnter(row, e)}
              onMouseMove={(e) => handleEnter(row, e)}
              onMouseLeave={handleLeave}
              onClick={() => row && onSelect?.(row.code)}
            />
          );
        })}
      </svg>

      {/* Sequential legend */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 8,
          fontFamily: CHART_THEME.fonts.ui,
          fontSize: 11,
          color: CHART_THEME.colors.textTertiary,
        }}
      >
        <span>Lower risk</span>
        <div
          style={{
            width: 160,
            height: 8,
            borderRadius: 4,
            background: `linear-gradient(90deg, ${CHART_THEME.colors.positive}, ${CHART_THEME.colors.highlight}, ${CHART_THEME.colors.warning}, ${CHART_THEME.colors.negative})`,
          }}
        />
        <span>Higher risk</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginLeft: 12 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: NO_DATA_FILL, display: 'inline-block' }} />
          No data
        </span>
      </div>

      {hovered && (
        <div
          style={{
            position: 'absolute',
            left: hovered.x,
            top: hovered.y - 12,
            transform: 'translate(-50%, -100%)',
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <ChartTooltip
            title={hovered.row.name}
            value={hovered.row.composite != null ? hovered.row.composite.toFixed(1) : '—'}
            {...(hovered.row.classification
              ? { benchmark: { label: 'Classification', value: hovered.row.classification } }
              : {})}
            {...(hovered.row.trend
              ? {
                  change: {
                    value: hovered.row.trend,
                    direction: hovered.row.trend.toUpperCase().includes('UP') || hovered.row.trend.toUpperCase().includes('WORSEN')
                      ? 'up'
                      : hovered.row.trend.toUpperCase().includes('DOWN') || hovered.row.trend.toUpperCase().includes('IMPROV')
                      ? 'down'
                      : 'flat',
                  },
                }
              : {})}
          />
        </div>
      )}
    </div>
  );
}

export default WorldRiskMap;
