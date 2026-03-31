import { useMemo } from 'react';
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
}

function herfindahl(positions: ConcentrationPosition[]): number {
  return positions.reduce((sum, p) => sum + (p.weight / 100) ** 2, 0) * 10000;
}

export function ConcentrationAnalysis({
  positions,
  topN = 10,
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
  const isConcentrated = top10Weight > 60;

  const maxWeight = top[0]?.weight ?? 1;

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  };

  const statsStyle: CSSProperties = {
    display: 'flex',
    gap: 'var(--space-4)',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-surface-raised)',
    borderRadius: 'var(--radius-sm)',
    border: isConcentrated
      ? '1px solid var(--color-signal-warning)'
      : '1px solid var(--color-surface-border)',
  };

  const statItemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  };

  const rowStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '60px 130px 1fr 70px 70px',
    gap: 'var(--space-2)',
    alignItems: 'center',
    padding: '5px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    transition: 'background 0.1s',
  };

  return (
    <div className="animate-in" style={rootStyle}>
      {/* Stats header */}
      <div style={statsStyle}>
        <div style={statItemStyle}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            HHI Index
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>
            {hhi.toFixed(0)}
          </span>
        </div>
        <div style={statItemStyle}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Top 10 Weight
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-sm)', color: isConcentrated ? 'var(--color-signal-warning)' : 'var(--color-text-primary)' }}>
            {top10Weight.toFixed(1)}%
            {isConcentrated && (
              <span style={{ marginLeft: '6px', fontSize: 'var(--text-xs)' }}>&#9888;</span>
            )}
          </span>
        </div>
        <div style={statItemStyle}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Positions
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>
            {positions.length}
          </span>
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

      {top.map((pos, _i) => {
        const barPct = (pos.weight / maxWeight) * 100;
        return (
          <div
            key={pos.ticker}
            style={rowStyle}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'transparent';
            }}
          >
            <span style={{ fontFamily: 'var(--font-data)', fontWeight: 700, color: 'var(--color-accent-primary)', fontSize: 'var(--text-xs)' }}>
              {pos.ticker}
            </span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {pos.name}
            </span>
            <div style={{ height: '6px', background: 'var(--color-surface-overlay)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${barPct}%`, background: 'var(--color-accent-primary)', borderRadius: '3px' }} />
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
