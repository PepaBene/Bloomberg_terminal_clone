import { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import { CHART_THEME } from '@/components/charts';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface NetworkNode {
  id: string;
  name: string;
  type: 'institution' | 'insider' | 'fund';
  shares: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  value: number;
}

export interface OwnershipNetworkProps {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const TYPE_COLORS: Record<NetworkNode['type'], string> = {
  institution: CHART_THEME.colors.series[0] as string,
  insider: CHART_THEME.colors.series[2] as string,
  fund: CHART_THEME.colors.series[3] as string,
};

const MIN_RADIUS = 6;
const MAX_RADIUS = 28;

/* ------------------------------------------------------------------ */
/*  Force simulation node interface                                    */
/* ------------------------------------------------------------------ */

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  type: NetworkNode['type'];
  shares: number;
  radius: number;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  value: number;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function OwnershipNetwork({ nodes, links }: OwnershipNetworkProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  /* Tooltip */
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    node: SimNode;
  } | null>(null);

  /* Observe container size */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setDimensions({
          width: entry.contentRect.width,
          height: Math.max(360, entry.contentRect.width * 0.6),
        });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* D3 force simulation */
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    if (!svgRef.current) return;

    svg.selectAll('*').remove();

    const { width, height } = dimensions;

    /* Radius scale */
    const sharesExtent = d3.extent(nodes, (n) => n.shares) as [number, number];
    const rScale = d3
      .scaleSqrt()
      .domain(sharesExtent[0] != null ? sharesExtent : [0, 1])
      .range([MIN_RADIUS, MAX_RADIUS]);

    /* Build simulation data */
    const simNodes: SimNode[] = nodes.map((n) => ({
      ...n,
      radius: rScale(n.shares),
    }));

    const simLinks: SimLink[] = links.map((l) => ({
      source: l.source,
      target: l.target,
      value: l.value,
    }));

    /* Root group for zoom/pan */
    const g = svg.append('g');

    /* Zoom behavior */
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        g.attr('transform', event.transform.toString());
      });

    svg.call(zoom as unknown as (selection: d3.Selection<SVGSVGElement | null, unknown, null, undefined>) => void);

    /* Links */
    const link = g
      .append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', CHART_THEME.colors.surfaceBorderStrong)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.max(1, Math.sqrt(d.value) * 0.5));

    /* Nodes */
    const node = g
      .append('g')
      .selectAll('circle')
      .data(simNodes)
      .join('circle')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => TYPE_COLORS[d.type])
      .attr('stroke', CHART_THEME.colors.surfaceBase)
      .attr('stroke-width', 1.5)
      .style('cursor', 'grab');

    /* Labels */
    const labels = g
      .append('g')
      .selectAll('text')
      .data(simNodes)
      .join('text')
      .text((d) => d.name.length > 12 ? d.name.slice(0, 12) + '\u2026' : d.name)
      .attr('font-family', CHART_THEME.fonts.ui)
      .attr('font-size', 9)
      .attr('fill', CHART_THEME.colors.textSecondary)
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => d.radius + 12)
      .style('pointer-events', 'none');

    /* Hover events on native DOM */
    node.on('mouseenter', function (_event: MouseEvent, d: SimNode) {
      d3.select(this).attr('stroke', CHART_THEME.colors.accent).attr('stroke-width', 2);
      setTooltip({ x: d.x ?? 0, y: d.y ?? 0, node: d });
    });
    node.on('mouseleave', function () {
      d3.select(this).attr('stroke', CHART_THEME.colors.surfaceBase).attr('stroke-width', 1.5);
      setTooltip(null);
    });

    /* Drag behavior */
    const drag = d3
      .drag<SVGCircleElement, SimNode>()
      .on('start', (event: d3.D3DragEvent<SVGCircleElement, SimNode, SimNode>, d: SimNode) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event: d3.D3DragEvent<SVGCircleElement, SimNode, SimNode>, d: SimNode) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event: d3.D3DragEvent<SVGCircleElement, SimNode, SimNode>, d: SimNode) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    node.call(drag as unknown as (selection: d3.Selection<SVGCircleElement | d3.BaseType, SimNode, SVGGElement, unknown>) => void);

    /* Force simulation */
    const simulation = d3
      .forceSimulation(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<SimNode>().radius((d) => d.radius + 4));

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0);

      node.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0);
      labels.attr('x', (d) => d.x ?? 0).attr('y', (d) => d.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, links, dimensions]);

  return (
    <div ref={containerRef} className="terminal-panel" style={{ position: 'relative', width: '100%' }}>
      {/* Header */}
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: 8,
        }}
      >
        Ownership Network
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
        {(['institution', 'insider', 'fund'] as const).map((type) => (
          <div
            key={type}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
              color: CHART_THEME.colors.textSecondary,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: TYPE_COLORS[type],
                flexShrink: 0,
              }}
            />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </div>
        ))}
      </div>

      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        style={{
          display: 'block',
          background: 'var(--color-surface-base)',
          borderRadius: 4,
          border: '1px solid var(--color-surface-border)',
        }}
      />

      {/* Tooltip (positioned via SVG coords — approximate overlay) */}
      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            /* offset for the header + legend area (~60px) */
            top: tooltip.y + 60,
            transform: 'translate(-50%, -100%)',
            background: CHART_THEME.colors.tooltip.bg,
            border: `1px solid ${CHART_THEME.colors.surfaceBorderStrong}`,
            borderRadius: 4,
            padding: '8px 10px',
            boxShadow: CHART_THEME.shadowFloat,
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: 140,
          }}
        >
          <div
            style={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 11,
              color: CHART_THEME.colors.tooltip.label,
              marginBottom: 2,
            }}
          >
            {tooltip.node.name}
          </div>
          <div
            style={{
              fontFamily: CHART_THEME.fonts.data,
              fontSize: 12,
              color: CHART_THEME.colors.tooltip.text,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            Shares: {tooltip.node.shares.toLocaleString()}
          </div>
          <div
            style={{
              fontFamily: CHART_THEME.fonts.ui,
              fontSize: 10,
              color: TYPE_COLORS[tooltip.node.type],
              marginTop: 2,
              textTransform: 'capitalize',
            }}
          >
            {tooltip.node.type}
          </div>
        </div>
      )}
    </div>
  );
}
