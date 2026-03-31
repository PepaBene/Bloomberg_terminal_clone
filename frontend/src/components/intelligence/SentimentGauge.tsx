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

const ZONE_RED = { from: -1, to: -0.3, color: 'var(--signal-negative)' };
const ZONE_NEUTRAL = { from: -0.3, to: 0.3, color: 'var(--signal-neutral)' };
const ZONE_GREEN = { from: 0.3, to: 1.0, color: 'var(--signal-positive)' };

const ZONES = [ZONE_RED, ZONE_NEUTRAL, ZONE_GREEN] as const;

const MOMENTUM_ARROWS: Record<string, string> = {
  IMPROVING: '\u2191',
  STABLE: '\u2192',
  DECLINING: '\u2193',
};

const MOMENTUM_COLORS: Record<string, string> = {
  IMPROVING: 'var(--signal-positive)',
  STABLE: 'var(--signal-neutral)',
  DECLINING: 'var(--signal-negative)',
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
  const momColor = MOMENTUM_COLORS[momKey] ?? 'var(--text-tertiary)';

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-3)',
      }}
    >
      {/* Label */}
      {label && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {label}
        </span>
      )}

      {/* Score + momentum */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-2)' }}>
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
          borderRadius: 'var(--radius-sm)',
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
            width: '2px',
            height: '14px',
            borderRadius: '1px',
            background: 'var(--accent-primary)',
            transform: 'translateX(-50%)',
            boxShadow: '0 0 6px var(--accent-primary)',
            transition: 'left var(--transition-slow)',
            animation: 'needlePulse 2s ease-in-out infinite',
          }}
        />
      </div>

      {/* Scale labels */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-tertiary)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span>-1.0</span>
        <span>0</span>
        <span>+1.0</span>
      </div>

      {/* Needle pulse animation */}
      <style>{`
        @keyframes needlePulse {
          0%, 100% { box-shadow: 0 0 4px var(--accent-primary); }
          50% { box-shadow: 0 0 10px var(--accent-primary); }
        }
      `}</style>
    </div>
  );
}
