import { useMemo } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SentimentGaugeProps {
  /** Sentiment value from -1 to +1 */
  value: number;
  /** Momentum direction: IMPROVING, STABLE, DECLINING */
  momentum?: string;
  /** Entity label displayed below the gauge */
  label?: string;
  /** Additional CSS class */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ZONE_RED = { from: -1, to: -0.3, color: 'var(--color-signal-negative)' };
const ZONE_NEUTRAL = { from: -0.3, to: 0.3, color: 'var(--color-signal-neutral)' };
const ZONE_GREEN = { from: 0.3, to: 1.0, color: 'var(--color-signal-positive)' };

const ZONES = [ZONE_RED, ZONE_NEUTRAL, ZONE_GREEN] as const;

const MOMENTUM_ARROWS: Record<string, string> = {
  IMPROVING: '\u2191',
  STABLE: '\u2192',
  DECLINING: '\u2193',
};

const MOMENTUM_COLORS: Record<string, string> = {
  IMPROVING: 'var(--color-signal-positive)',
  STABLE: 'var(--color-signal-neutral)',
  DECLINING: 'var(--color-signal-negative)',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function valueColor(v: number): string {
  if (v <= -0.3) return ZONE_RED.color;
  if (v >= 0.3) return ZONE_GREEN.color;
  return ZONE_NEUTRAL.color;
}

/** Map a -1..+1 value to a 0..100% position */
function valueToPct(v: number): number {
  return ((Math.max(-1, Math.min(1, v)) + 1) / 2) * 100;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function SentimentGauge({
  value,
  momentum,
  label,
  className,
}: SentimentGaugeProps) {
  const clamped = Math.max(-1, Math.min(1, value));
  const pct = useMemo(() => valueToPct(clamped), [clamped]);
  const needleColor = valueColor(clamped);
  const momKey = momentum?.toUpperCase() ?? '';
  const momArrow = MOMENTUM_ARROWS[momKey] ?? '';
  const momColor = MOMENTUM_COLORS[momKey] ?? 'var(--color-text-tertiary)';

  return (
    <div className={clsx('flex flex-col gap-2', className)}>
      {/* Label */}
      {label && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {label}
        </span>
      )}

      {/* Score + momentum */}
      <div className="flex items-baseline gap-2">
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            color: needleColor,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1,
          }}
        >
          {clamped >= 0 ? '+' : ''}
          {clamped.toFixed(2)}
        </span>
        {momentum && (
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              color: momColor,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {momArrow} {momentum}
          </span>
        )}
      </div>

      {/* Horizontal bar */}
      <div
        style={{
          position: 'relative',
          height: 10,
          borderRadius: 5,
          overflow: 'hidden',
          display: 'flex',
        }}
      >
        {ZONES.map((z) => {
          const left = valueToPct(z.from);
          const right = valueToPct(z.to);
          return (
            <div
              key={z.from}
              style={{
                position: 'absolute',
                left: `${left}%`,
                width: `${right - left}%`,
                height: '100%',
                background: z.color,
                opacity: 0.25,
              }}
            />
          );
        })}

        {/* Needle / marker */}
        <div
          style={{
            position: 'absolute',
            left: `${pct}%`,
            top: '-2px',
            width: '3px',
            height: '14px',
            borderRadius: '1.5px',
            background: needleColor,
            transform: 'translateX(-50%)',
            boxShadow: `0 0 6px ${needleColor}`,
            transition: 'left 0.3s ease',
          }}
        />
      </div>

      {/* Scale labels */}
      <div
        className="flex items-center justify-between"
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: '9px',
          color: 'var(--color-text-tertiary)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span>-1.0</span>
        <span>0</span>
        <span>+1.0</span>
      </div>
    </div>
  );
}
