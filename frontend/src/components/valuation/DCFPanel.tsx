import { useState, useEffect, useRef } from 'react';
import { SensitivityMatrix } from './SensitivityMatrix';
import { PanelProgress } from '../feedback/PanelProgress';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DCFAssumptions {
  wacc: number;
  terminalGrowth: number;
  projectionYears: number;
  currentFCF: number;
}

export interface DCFResult {
  enterpriseValue: number;
  equityValue: number;
  impliedPrice: number;
  currentPrice: number;
  upside: number;
}

export interface DCFSensitivity {
  waccRange: number[];
  growthRange: number[];
  matrix: number[][];
}

export interface DCFScenario {
  label: string;
  impliedPrice: number;
  upside: number;
  tier: 'bull' | 'base' | 'bear';
}

export interface DCFPanelProps {
  assumptions: DCFAssumptions;
  result: DCFResult;
  sensitivity?: DCFSensitivity;
  scenarios?: DCFScenario[];
  onRecalculate?: () => Promise<void>;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtCurrency(value: number): string {
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toFixed(2)}`;
}

function fmtPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtUpside(value: number): string {
  const pct = (value * 100).toFixed(1);
  if (value > 0) return `+${pct}%`;
  if (value < 0) return `${pct}%`;
  return `${pct}%`;
}

function scenarioColor(tier: DCFScenario['tier']): string {
  switch (tier) {
    case 'bull':
      return 'var(--color-quality-5)';
    case 'base':
      return 'var(--color-quality-3)';
    case 'bear':
      return 'var(--color-quality-1)';
  }
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DCFPanel({ assumptions, result, sensitivity, scenarios, onRecalculate }: DCFPanelProps) {
  const [isComputing, setIsComputing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const upsideColor =
    result.upside > 0
      ? 'var(--color-signal-positive)'
      : result.upside < 0
        ? 'var(--color-signal-negative)'
        : 'var(--color-text-primary)';

  const upsideLabel = result.upside > 0 ? 'Upside' : result.upside < 0 ? 'Downside' : 'At Fair Value';

  const startComputing = async () => {
    setIsComputing(true);
    setElapsed(0);
    intervalRef.current = setInterval(() => {
      setElapsed((e) => e + 0.1);
    }, 100);

    if (onRecalculate) {
      try {
        await onRecalculate();
      } finally {
        stopComputing();
      }
    }
  };

  const stopComputing = () => {
    setIsComputing(false);
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setElapsed(0);
  };

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return (
    <div className="terminal-panel animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
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
          DCF Model Summary
        </div>
        <button
          type="button"
          onClick={isComputing ? stopComputing : startComputing}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: isComputing ? 'var(--color-signal-negative)' : 'var(--color-accent-primary)',
            background: 'transparent',
            border: `1px solid ${isComputing ? 'var(--color-signal-negative)' : 'var(--color-accent-primary)'}`,
            borderRadius: 'var(--radius-sm)',
            padding: '2px 8px',
            cursor: 'pointer',
            transition: 'opacity var(--transition-fast)',
          }}
        >
          {isComputing ? 'Cancel' : 'Run DCF'}
        </button>
      </div>

      {/* DCF content area — position: relative required for PanelProgress overlay */}
      <div style={{ position: 'relative' }}>
        {/* Dim overlay (renders above content when computing) */}
        <PanelProgress
          loading={isComputing}
          dimContent={isComputing}
          statusMessage="Running DCF…"
          elapsedSeconds={elapsed}
        />

        {/* Key Assumptions -- 2-column grid */}
        <div>
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: 'var(--space-2)',
            }}
          >
            Key Assumptions
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0',
            }}
          >
            <AssumptionRow label="WACC" value={fmtPct(assumptions.wacc)} />
            <AssumptionRow label="Terminal Growth" value={fmtPct(assumptions.terminalGrowth)} />
            <AssumptionRow label="Projection Years" value={String(assumptions.projectionYears)} />
            <AssumptionRow label="Current FCF" value={fmtCurrency(assumptions.currentFCF)} />
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--color-surface-border)', margin: 'var(--space-4) 0' }} />

        {/* Result Summary */}
        <div>
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: 'var(--space-2)',
            }}
          >
            Valuation Result
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0',
            }}
          >
            <AssumptionRow label="Enterprise Value" value={fmtCurrency(result.enterpriseValue)} />
            <AssumptionRow label="Equity Value" value={fmtCurrency(result.equityValue)} />
          </div>

          {/* Implied price vs current price hero row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 'var(--space-3)',
              marginTop: 'var(--space-3)',
              padding: 'var(--space-3)',
              background: 'var(--color-surface-raised)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-surface-border)',
            }}
          >
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-1)',
                }}
              >
                Implied Price
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-2xl)',
                  fontWeight: 600,
                  color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums' as const,
                }}
              >
                ${result.impliedPrice.toFixed(2)}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-1)',
                }}
              >
                Current Price
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-lg)',
                  color: 'var(--color-text-tertiary)',
                  fontVariantNumeric: 'tabular-nums' as const,
                }}
              >
                ${result.currentPrice.toFixed(2)}
              </div>
            </div>
            <div>
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-1)',
                }}
              >
                {upsideLabel}
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-lg)',
                  fontWeight: 600,
                  color: upsideColor,
                  fontVariantNumeric: 'tabular-nums' as const,
                }}
              >
                {fmtUpside(result.upside)}
              </div>
            </div>
          </div>
        </div>

        {/* Bull / Base / Bear Scenarios */}
        {scenarios && scenarios.length > 0 && (
          <>
            <div style={{ height: 1, background: 'var(--color-surface-border)', margin: 'var(--space-4) 0' }} />
            <div>
              <div
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  marginBottom: 'var(--space-2)',
                }}
              >
                Scenario Analysis
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                {scenarios.map((s) => (
                  <ScenarioCard key={s.label} scenario={s} />
                ))}
              </div>
            </div>
          </>
        )}

        {/* Optional Sensitivity Matrix */}
        {sensitivity && (
          <>
            <div style={{ height: 1, background: 'var(--color-surface-border)', margin: 'var(--space-4) 0' }} />
            <SensitivityMatrix
              waccValues={sensitivity.waccRange}
              growthValues={sensitivity.growthRange}
              priceMatrix={sensitivity.matrix}
              currentPrice={result.currentPrice}
            />
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function AssumptionRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: 'var(--space-1) var(--space-2)',
        borderRadius: 'var(--radius-sm)',
        transition: 'background 120ms ease',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--color-surface-overlay)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-primary)',
          fontVariantNumeric: 'tabular-nums' as const,
        }}
      >
        {value}
      </span>
    </div>
  );
}

function ScenarioCard({ scenario }: { scenario: DCFScenario }) {
  const color = scenarioColor(scenario.tier);
  const upsideStr = fmtUpside(scenario.upside);

  return (
    <div
      style={{
        flex: 1,
        padding: 'var(--space-2) var(--space-3)',
        background: 'var(--color-surface-raised)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--radius-sm)',
        borderTop: `2px solid ${color}`,
        transition: 'background 120ms ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--color-surface-overlay)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--color-surface-raised)';
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: 'var(--space-1)',
        }}
      >
        {scenario.label}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-lg)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          fontVariantNumeric: 'tabular-nums' as const,
        }}
      >
        ${scenario.impliedPrice.toFixed(2)}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xs)',
          color,
          fontVariantNumeric: 'tabular-nums' as const,
          marginTop: 'var(--space-1)',
        }}
      >
        {upsideStr}
      </div>
    </div>
  );
}
