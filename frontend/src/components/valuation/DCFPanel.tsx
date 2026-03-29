import { SensitivityMatrix } from './SensitivityMatrix';

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

export interface DCFPanelProps {
  assumptions: DCFAssumptions;
  result: DCFResult;
  sensitivity?: DCFSensitivity;
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

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DCFPanel({ assumptions, result, sensitivity }: DCFPanelProps) {
  const upsideColor =
    result.upside > 0
      ? 'var(--color-signal-positive)'
      : result.upside < 0
        ? 'var(--color-signal-negative)'
        : 'var(--color-text-primary)';

  const upsideLabel = result.upside > 0 ? 'Upside' : result.upside < 0 ? 'Downside' : 'At Fair Value';

  return (
    <div className="terminal-panel flex flex-col gap-4">
      {/* Header */}
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

      {/* Key Assumptions — 2-column grid */}
      <div>
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: 6,
          }}
        >
          Key Assumptions
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '6px 16px',
          }}
        >
          <AssumptionRow label="WACC" value={fmtPct(assumptions.wacc)} />
          <AssumptionRow label="Terminal Growth" value={fmtPct(assumptions.terminalGrowth)} />
          <AssumptionRow label="Projection Years" value={String(assumptions.projectionYears)} />
          <AssumptionRow label="Current FCF" value={fmtCurrency(assumptions.currentFCF)} />
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'var(--color-surface-border)' }} />

      {/* Result Summary */}
      <div>
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: 6,
          }}
        >
          Valuation Result
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '6px 16px',
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
            gap: 12,
            marginTop: 12,
            padding: '10px 12px',
            background: 'var(--color-surface-raised)',
            borderRadius: 4,
            border: '1px solid var(--color-surface-border)',
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
                marginBottom: 2,
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
                fontVariantNumeric: 'tabular-nums',
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
                marginBottom: 2,
              }}
            >
              Current Price
            </div>
            <div
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-lg)',
                color: 'var(--color-text-tertiary)',
                fontVariantNumeric: 'tabular-nums',
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
                marginBottom: 2,
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
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {result.upside > 0 ? '+' : ''}{(result.upside * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Optional Sensitivity Matrix */}
      {sensitivity && (
        <>
          <div style={{ height: 1, background: 'var(--color-surface-border)' }} />
          <SensitivityMatrix
            waccValues={sensitivity.waccRange}
            growthValues={sensitivity.growthRange}
            priceMatrix={sensitivity.matrix}
            currentPrice={result.currentPrice}
          />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function AssumptionRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
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
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </div>
  );
}
