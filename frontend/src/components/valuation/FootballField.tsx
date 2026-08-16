import { useMemo, useState } from 'react';
import { ChartTooltip } from '../charts/ChartTooltip';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

// Mirrors backend `ValuationMethodRange` (src/schemas/analytics.py) as
// returned by `GET /v2/analytics/valuation/{id}/summary`.
export interface FootballFieldMethodology {
  methodology: string;
  low: number | null;
  mid: number | null;
  high: number | null;
  confidence: string | null;
}

export interface FootballFieldProps {
  methodologies: FootballFieldMethodology[];
  currentPrice?: number | null;
  consensusView?: string | null;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CONFIDENCE_COLOR: Record<string, string> = {
  HIGH: 'var(--color-signal-positive)',
  MEDIUM: 'var(--color-signal-neutral)',
  LOW: 'var(--color-signal-negative)',
};

function fmtMethodologyLabel(m: string): string {
  return m
    .split('_')
    .map((w) => (w.length > 0 ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w))
    .join(' ');
}

function fmtPrice(v: number): string {
  return `$${v.toFixed(2)}`;
}

/** ~5 evenly spaced, clean-ish axis ticks spanning [min, max]. */
function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [min, max];
  const span = max - min;
  const rawStep = span / (count - 1);
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / magnitude;
  const step = (residual >= 5 ? 10 : residual >= 2 ? 5 : residual >= 1 ? 2 : 1) * magnitude;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let t = start; t <= max + step * 0.001; t += step) ticks.push(Math.round(t * 100) / 100);
  return ticks.length > 0 ? ticks : [min, max];
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Standard valuation "football field" chart — a horizontal bar per
 * methodology (DCF, comps, precedent transactions, 52-week range, etc.)
 * showing its low/mid/high implied-value range, with the current price
 * marked as a vertical reference line across all rows.
 *
 * Renders exactly the fields the backend actually returns
 * (`GET /v2/analytics/valuation/{id}/summary` → `FootballFieldResponse`):
 * `methodology`, `low`, `mid`, `high`, `confidence` per row, plus
 * `current_price` / `consensus_view` at the top level. No fabricated data.
 */
export function FootballField({ methodologies, currentPrice, consensusView }: FootballFieldProps) {
  const rows = useMemo(
    () =>
      (Array.isArray(methodologies) ? methodologies : []).filter(
        (m): m is FootballFieldMethodology => typeof m?.low === 'number' && typeof m?.high === 'number',
      ),
    [methodologies],
  );

  const { domainMin, domainMax } = useMemo(() => {
    const values: number[] = [];
    rows.forEach((m) => {
      if (typeof m.low === 'number') values.push(m.low);
      if (typeof m.mid === 'number') values.push(m.mid);
      if (typeof m.high === 'number') values.push(m.high);
    });
    if (typeof currentPrice === 'number') values.push(currentPrice);

    if (values.length === 0) return { domainMin: 0, domainMax: 1 };

    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.1 || Math.max(Math.abs(max) * 0.1, 1);
    return { domainMin: Math.max(0, min - pad), domainMax: max + pad };
  }, [rows, currentPrice]);

  const toPct = (v: number) => {
    const span = domainMax - domainMin || 1;
    return ((v - domainMin) / span) * 100;
  };

  const axisTicks = useMemo(() => niceTicks(domainMin, domainMax), [domainMin, domainMax]);
  const hasConfidence = rows.some((m) => m.confidence);
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="terminal-panel" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Football Field
        {consensusView && (
          <span
            style={{
              marginLeft: 8,
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              color: 'var(--color-text-secondary)',
              textTransform: 'none',
              letterSpacing: 'normal',
            }}
          >
            — {consensusView.replace(/_/g, ' ')}
          </span>
        )}
      </div>

      {hasConfidence && rows.length > 0 && (
        <div style={{ display: 'flex', gap: 'var(--space-4)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
          {(['HIGH', 'MEDIUM', 'LOW'] as const).map((c) => (
            <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: CONFIDENCE_COLOR[c] }} />
              {c.charAt(0) + c.slice(1).toLowerCase()} confidence
            </span>
          ))}
        </div>
      )}

      {rows.length === 0 ? (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
            padding: 'var(--space-3) 0',
          }}
        >
          No football-field valuation data available.
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', paddingTop: 4 }}>
            {rows.map((m) => {
              const low = m.low as number;
              const high = m.high as number;
              const mid = typeof m.mid === 'number' ? m.mid : (low + high) / 2;
              const left = toPct(low);
              const width = Math.max(toPct(high) - left, 0.5);
              const color = (m.confidence && CONFIDENCE_COLOR[m.confidence.toUpperCase()]) || 'var(--color-chart-1)';

              return (
                <div key={m.methodology} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 140,
                      flexShrink: 0,
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    {fmtMethodologyLabel(m.methodology)}
                  </div>
                  <div
                    style={{
                      position: 'relative',
                      flex: 1,
                      height: 20,
                      background: 'var(--color-surface-raised)',
                      border: `1px solid ${hovered === m.methodology ? 'var(--color-accent-primary)' : 'var(--color-surface-border)'}`,
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'default',
                    }}
                    onMouseEnter={() => setHovered(m.methodology)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: `${left}%`,
                        width: `${width}%`,
                        background: color,
                        opacity: hovered === m.methodology ? 0.65 : 0.45,
                        borderRadius: 'var(--radius-sm)',
                        transition: 'opacity var(--transition-fast)',
                      }}
                    />
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: `${toPct(mid)}%`,
                        width: 2,
                        background: color,
                      }}
                    />
                    {typeof currentPrice === 'number' && (
                      <div
                        title={`Current price: ${fmtPrice(currentPrice)}`}
                        style={{
                          position: 'absolute',
                          top: -2,
                          bottom: -2,
                          left: `${toPct(currentPrice)}%`,
                          width: 1,
                          background: 'var(--color-accent-primary)',
                          pointerEvents: 'none',
                        }}
                      />
                    )}

                    {hovered === m.methodology && (
                      <div
                        style={{
                          position: 'absolute',
                          left: `${toPct(mid)}%`,
                          bottom: '100%',
                          transform: 'translateX(-50%)',
                          marginBottom: 6,
                          zIndex: 10,
                          pointerEvents: 'none',
                        }}
                      >
                        <ChartTooltip
                          title={fmtMethodologyLabel(m.methodology)}
                          value={fmtPrice(mid)}
                          series={[
                            { name: 'Low', value: fmtPrice(low), color },
                            { name: 'High', value: fmtPrice(high), color },
                          ]}
                          {...(m.confidence ? { benchmark: { label: 'Confidence', value: m.confidence } } : {})}
                        />
                      </div>
                    )}
                  </div>
                  <div
                    style={{
                      width: 200,
                      flexShrink: 0,
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-text-primary)',
                      textAlign: 'right',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {fmtPrice(low)} – {fmtPrice(high)}{' '}
                    <span style={{ color: 'var(--color-text-tertiary)' }}>(mid {fmtPrice(mid)})</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Price axis — aligned under the range tracks (140px label + 200px value columns) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 140, flexShrink: 0 }} />
            <div style={{ position: 'relative', flex: 1, height: 14 }}>
              {axisTicks.map((t) => (
                <span
                  key={t}
                  style={{
                    position: 'absolute',
                    left: `${toPct(t)}%`,
                    transform: 'translateX(-50%)',
                    fontFamily: 'var(--font-data)',
                    fontVariantNumeric: 'tabular-nums',
                    fontSize: 10,
                    color: 'var(--color-text-tertiary)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {fmtPrice(t)}
                </span>
              ))}
            </div>
            <div style={{ width: 200, flexShrink: 0 }} />
          </div>

          {typeof currentPrice === 'number' && (
            <div
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-tertiary)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span style={{ width: 8, height: 2, background: 'var(--color-accent-primary)', display: 'inline-block' }} />
              Current price: {fmtPrice(currentPrice)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
