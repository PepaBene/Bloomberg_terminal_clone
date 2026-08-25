import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';

export interface ConcentrationPosition {
  name: string;
  ticker: string;
  weight: number;
  varContrib: number;
}

export interface ConcentrationAnalysisProps {
  positions: ConcentrationPosition[];
  topN?: number;
  /** Top-10 weight (%) above which the book is flagged as concentrated */
  concentrationThreshold?: number;
}

function herfindahl(positions: ConcentrationPosition[]): number {
  return positions.reduce((sum, p) => sum + (p.weight / 100) ** 2, 0) * 10000;
}

/* ------------------------------------------------------------------ */
/*  Meter — a single ratio against a limit, same-ramp track            */
/* ------------------------------------------------------------------ */

function ConcentrationMeter({ value, limit }: { value: number; limit: number }) {
  const pct = Math.min((value / Math.max(limit * 1.4, value, 1)) * 100, 100);
  const overLimit = value > limit;
  const fillColor = overLimit ? 'var(--color-signal-warning)' : 'var(--color-accent-primary)';
  const limitPct = Math.min((limit / Math.max(limit * 1.4, value, 1)) * 100, 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 140 }}>
      <div
        style={{
          position: 'relative',
          height: 8,
          borderRadius: 4,
          background: 'color-mix(in srgb, var(--color-accent-primary) 12%, var(--color-surface-overlay))',
          overflow: 'visible',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: `${pct}%`,
            borderRadius: 4,
            background: fillColor,
            transition: 'width var(--transition-normal)',
          }}
        />
        <div
          title={`Threshold: ${limit.toFixed(0)}%`}
          style={{
            position: 'absolute',
            top: -2,
            bottom: -2,
            left: `${limitPct}%`,
            width: 2,
            background: 'var(--color-text-tertiary)',
          }}
        />
      </div>
    </div>
  );
}

export function ConcentrationAnalysis({
  positions,
  topN = 10,
  concentrationThreshold = 60,
}: ConcentrationAnalysisProps) {
  const sorted = useMemo(
    () => [...positions].sort((a, b) => b.weight - a.weight),
    [positions],
  );

  const top = sorted.slice(0, topN);
  const hhi = useMemo(() => herfindahl(positions), [positions]);
  const top10Weight = useMemo(
    () => sorted.slice(0, 10).reduce((s, p) => s + p.weight, 0),
    [sorted],
  );
  const isConcentrated = top10Weight > concentrationThreshold;

  const maxWeight = top[0]?.weight ?? 1;
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  };

  const statsStyle: CSSProperties = {
    display: 'flex',
    gap: 'var(--space-5)',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-surface-raised)',
    borderRadius: 'var(--radius-sm)',
    border: isConcentrated
      ? '1px solid var(--color-signal-warning)'
      : '1px solid var(--color-surface-border)',
    alignItems: 'center',
    flexWrap: 'wrap',
  };

  const statItemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  };

  const statLabelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  const statValueStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontVariantNumeric: 'tabular-nums',
    fontSize: 'var(--text-sm)',
    color: 'var(--color-text-primary)',
  };

  const rowStyle = (ticker: string): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '60px 130px 1fr 70px 70px',
    gap: 'var(--space-2)',
    alignItems: 'center',
    padding: '5px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    background: hoveredTicker === ticker ? 'var(--color-surface-raised)' : 'transparent',
    transition: 'background 0.1s',
  });

  return (
    <div className="animate-in" style={rootStyle}>
      {/* Stats header */}
      <div style={statsStyle}>
        <div style={statItemStyle}>
          <span style={statLabelStyle}>HHI Index</span>
          <span style={statValueStyle}>{hhi.toFixed(0)}</span>
        </div>
        <div style={statItemStyle}>
          <span style={statLabelStyle}>Positions</span>
          <span style={statValueStyle}>{positions.length}</span>
        </div>
        <div style={{ ...statItemStyle, flex: 1, minWidth: 180 }}>
          <span style={statLabelStyle}>
            Top 10 Weight vs {concentrationThreshold}% Limit
            {isConcentrated && <span style={{ marginLeft: 6, color: 'var(--color-signal-warning)' }}>&#9888;</span>}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ ...statValueStyle, color: isConcentrated ? 'var(--color-signal-warning)' : 'var(--color-text-primary)' }}>
              {top10Weight.toFixed(1)}%
            </span>
            <ConcentrationMeter value={top10Weight} limit={concentrationThreshold} />
          </div>
        </div>
      </div>

      {/* Table header */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '60px 130px 1fr 70px 70px',
          gap: 'var(--space-2)',
          padding: '4px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        <span>Ticker</span>
        <span>Name</span>
        <span>Weight</span>
        <span style={{ textAlign: 'right' }}>Weight %</span>
        <span style={{ textAlign: 'right' }}>VaR Contrib</span>
      </div>

      {top.map((pos) => {
        const barPct = (pos.weight / maxWeight) * 100;
        return (
          <div
            key={pos.ticker}
            style={rowStyle(pos.ticker)}
            onMouseEnter={() => setHoveredTicker(pos.ticker)}
            onMouseLeave={() => setHoveredTicker(null)}
            title={`${pos.name} — ${pos.weight.toFixed(2)}% of portfolio, ${pos.varContrib.toFixed(2)}% of VaR`}
          >
            <span style={{ fontFamily: 'var(--font-data)', fontWeight: 700, color: 'var(--color-accent-primary)', fontSize: 'var(--text-xs)' }}>
              {pos.ticker}
            </span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {pos.name}
            </span>
            <div style={{ height: 6, background: 'var(--color-surface-overlay)', borderRadius: 3, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${barPct}%`,
                  background: 'var(--color-accent-primary)',
                  borderRadius: 3,
                  transition: 'width var(--transition-normal)',
                }}
              />
            </div>
            <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)', textAlign: 'right' }}>
              {pos.weight.toFixed(1)}%
            </span>
            <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)', textAlign: 'right' }}>
              {pos.varContrib.toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default ConcentrationAnalysis;
