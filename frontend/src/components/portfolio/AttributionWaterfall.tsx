import type { CSSProperties } from 'react';

export interface AttributionSegment {
  label: string;
  contribution: number;
  type: 'allocation' | 'selection' | 'interaction' | 'total';
}

export interface AttributionWaterfallProps {
  segments: AttributionSegment[];
}

function barColor(contribution: number, isTotal: boolean): string {
  if (isTotal) return 'var(--color-accent-primary)';
  if (contribution > 0) return 'var(--color-signal-positive)';
  if (contribution < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-tertiary)';
}

export function AttributionWaterfall({ segments }: AttributionWaterfallProps) {
  const maxAbs = Math.max(...segments.map((s) => Math.abs(s.contribution)), 0.001);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  const rowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    height: '28px',
  };

  const labelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-secondary)',
    width: '100px',
    flexShrink: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };

  const trackStyle: CSSProperties = {
    flex: 1,
    height: '12px',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  };

  const valueStyle = (color: string): CSSProperties => ({
    fontFamily: 'var(--font-data)',
    fontSize: 'var(--text-xs)',
    fontVariantNumeric: 'tabular-nums',
    color,
    width: '60px',
    textAlign: 'right',
    flexShrink: 0,
  });

  return (
    <div className="animate-in" style={rootStyle}>
      {segments.map((seg, i) => {
        const isTotal = seg.type === 'total';
        const color = barColor(seg.contribution, isTotal);
        const barPct = (Math.abs(seg.contribution) / maxAbs) * 50; // max 50% of track width
        const sign = seg.contribution >= 0 ? '+' : '';

        return (
          <div key={i} style={rowStyle}>
            <span
              style={{
                ...labelStyle,
                fontWeight: isTotal ? 700 : 400,
                color: isTotal ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                borderTop: isTotal ? '1px solid var(--color-surface-border)' : undefined,
                paddingTop: isTotal ? 'var(--space-1)' : undefined,
              }}
            >
              {seg.label}
            </span>

            <div style={trackStyle}>
              {/* Center axis */}
              <div
                style={{
                  position: 'absolute',
                  left: '50%',
                  top: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: '1px',
                  height: '20px',
                  background: 'var(--color-surface-border)',
                }}
              />
              {/* Bar */}
              <div
                style={{
                  position: 'absolute',
                  height: isTotal ? '14px' : '10px',
                  width: `${barPct}%`,
                  left: seg.contribution >= 0 ? '50%' : `calc(50% - ${barPct}%)`,
                  background: color,
                  borderRadius: '2px',
                  opacity: isTotal ? 1 : 0.85,
                }}
              />
            </div>

            <span style={valueStyle(color)}>
              {sign}{seg.contribution.toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default AttributionWaterfall;
