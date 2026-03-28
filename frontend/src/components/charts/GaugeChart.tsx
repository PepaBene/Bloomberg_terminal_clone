import { useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface GaugeThreshold {
  value: number;
  color: string;
  label: string;
}

export interface GaugeChartProps {
  /** Current value */
  value: number;
  /** Maximum value (default 100) */
  max?: number;
  /** Label displayed below the gauge */
  label: string;
  /** Gauge diameter in px (default 120) */
  size?: number;
  /** Colored threshold segments; defaults to quality-1..5 at 20% intervals */
  thresholds?: GaugeThreshold[];
  /** Additional CSS class */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Default thresholds (quality-1 through quality-5)                   */
/* ------------------------------------------------------------------ */

const DEFAULT_THRESHOLDS: GaugeThreshold[] = [
  { value: 20, color: '#E05252', label: 'Very Low' },
  { value: 40, color: '#E0923A', label: 'Low' },
  { value: 60, color: '#D4A843', label: 'Moderate' },
  { value: 80, color: '#6DBF6D', label: 'Good' },
  { value: 100, color: '#2DB87D', label: 'Excellent' },
];

/* ------------------------------------------------------------------ */
/*  Geometry helpers                                                   */
/* ------------------------------------------------------------------ */

function polarToXY(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

/** SVG arc path from startDeg to endDeg (measured counter-clockwise from 3-o'clock) */
function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToXY(cx, cy, r, startDeg);
  const e = polarToXY(cx, cy, r, endDeg);
  const sweep = startDeg - endDeg > 180 ? 1 : 0;
  // Arc goes clockwise in SVG when sweep-flag=1
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${sweep} 0 ${e.x} ${e.y}`;
}

function colorForValue(value: number, max: number, thresholds: GaugeThreshold[]): string {
  const pct = (value / max) * 100;
  for (const t of thresholds) {
    if (pct <= t.value) return t.color;
  }
  return thresholds[thresholds.length - 1]?.color ?? '#E8EDF2';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function GaugeChart({
  value,
  max = 100,
  label,
  size = 120,
  thresholds,
  className,
}: GaugeChartProps) {
  const t = thresholds ?? DEFAULT_THRESHOLDS;
  const strokeW = Math.max(size * 0.09, 4);
  const r = (size - strokeW) / 2;
  const cx = size / 2;
  const cy = size / 2;

  const clamped = Math.min(Math.max(value, 0), max);
  // Map value to angle: 180 (left, min) down to 0 (right, max)
  const needleDeg = 180 - (clamped / max) * 180;
  const needleTip = polarToXY(cx, cy, r - 6, needleDeg);
  const needleColor = colorForValue(clamped, max, t);

  // Build colored arc segments
  const segments = useMemo(() => {
    const segs: { d: string; color: string }[] = [];
    let prevPct = 0;
    for (const seg of t) {
      const pct = Math.min(seg.value, 100);
      // Angles: 180 = leftmost, 0 = rightmost
      const aDeg = 180 - (prevPct / 100) * 180;
      const bDeg = 180 - (pct / 100) * 180;
      if (aDeg > bDeg) {
        segs.push({ d: arcPath(cx, cy, r, aDeg, bDeg), color: seg.color });
      }
      prevPct = pct;
    }
    return segs;
  }, [t, cx, cy, r]);

  const svgH = size * 0.58;

  return (
    <div className={clsx('inline-flex flex-col items-center', className)}>
      <svg width={size} height={svgH} viewBox={`0 ${cy - r - strokeW} ${size} ${r + strokeW + 20}`}>
        {/* Background arc */}
        <path
          d={arcPath(cx, cy, r, 180, 0)}
          fill="none"
          stroke="#171C22"
          strokeWidth={strokeW}
          strokeLinecap="round"
        />

        {/* Colored segments */}
        {segments.map((seg, i) => (
          <path
            key={i}
            d={seg.d}
            fill="none"
            stroke={seg.color}
            strokeWidth={strokeW}
            strokeLinecap="butt"
            opacity={0.55}
          />
        ))}

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleTip.x}
          y2={needleTip.y}
          stroke={needleColor}
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={3} fill={needleColor} />

        {/* Value */}
        <text
          x={cx}
          y={cy + 16}
          textAnchor="middle"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: size * 0.17,
            fontWeight: 600,
            fill: needleColor,
          }}
        >
          {Number.isInteger(clamped) ? clamped : clamped.toFixed(1)}
        </text>
      </svg>

      {/* Label */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginTop: 2,
          textAlign: 'center',
        }}
      >
        {label}
      </span>
    </div>
  );
}
