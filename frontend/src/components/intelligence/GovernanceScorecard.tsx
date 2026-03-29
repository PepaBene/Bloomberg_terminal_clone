import clsx from 'clsx';
import { GaugeChart } from '../charts/GaugeChart';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface RedFlag {
  id: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export interface GovernanceScorecardProps {
  /** Overall governance score 0-100 */
  score: number;
  /** Classification label (e.g. STRONG, ADEQUATE, WEAK) */
  classification: string;
  /** List of red flags */
  redFlags: RedFlag[];
  /** Board independence percentage 0-100 */
  boardIndependence: number;
  /** Whether the CEO is also Chair */
  ceoIsChair: boolean;
  /** Pay alignment score 0-100 */
  payAlignment: number;
  /** Additional CSS class */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'var(--color-signal-negative)',
  HIGH: 'var(--color-signal-warning)',
  MEDIUM: 'var(--color-signal-neutral)',
};

const SEVERITY_ICONS: Record<string, string> = {
  CRITICAL: '\u26D4',
  HIGH: '\u26A0',
  MEDIUM: '\u25CF',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function qualityColor(pct: number): string {
  if (pct >= 80) return 'var(--color-quality-5)';
  if (pct >= 60) return 'var(--color-quality-4)';
  if (pct >= 40) return 'var(--color-quality-3)';
  if (pct >= 20) return 'var(--color-quality-2)';
  return 'var(--color-quality-1)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function GovernanceScorecard({
  score,
  classification,
  redFlags,
  boardIndependence,
  ceoIsChair,
  payAlignment,
  className,
}: GovernanceScorecardProps) {
  const scoreColor = qualityColor(score);

  return (
    <div
      className={clsx('flex flex-col gap-4', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '16px',
      }}
    >
      {/* Header: gauge + classification */}
      <div className="flex items-center gap-4">
        <GaugeChart value={score} max={100} label="Governance" size={100} />
        <div className="flex flex-col gap-1">
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              color: scoreColor,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '2px 8px',
              border: `1px solid ${scoreColor}`,
              borderRadius: '9999px',
              whiteSpace: 'nowrap',
              alignSelf: 'flex-start',
            }}
          >
            {classification}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="flex flex-col gap-3">
        {/* Board Independence */}
        <MetricBar
          label="Board Independence"
          value={boardIndependence}
          suffix="%"
        />

        {/* CEO / Chair Separation */}
        <div className="flex items-center justify-between">
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-primary)',
            }}
          >
            CEO / Chair Separation
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              color: ceoIsChair
                ? 'var(--color-signal-negative)'
                : 'var(--color-signal-positive)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            {ceoIsChair ? '\u2715 COMBINED' : '\u2713 SEPARATED'}
          </span>
        </div>

        {/* Pay Alignment */}
        <MetricBar label="Pay Alignment" value={payAlignment} suffix="/100" />
      </div>

      {/* Red flags */}
      {redFlags.length > 0 && (
        <div className="flex flex-col gap-2">
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Red Flags ({redFlags.length})
          </span>
          {redFlags.map((flag) => {
            const sevColor =
              SEVERITY_COLORS[flag.severity] ?? 'var(--color-signal-neutral)';
            const sevIcon = SEVERITY_ICONS[flag.severity] ?? '\u25CF';

            return (
              <div
                key={flag.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '6px 8px',
                  background: 'var(--color-surface-raised)',
                  borderLeft: `3px solid ${sevColor}`,
                  borderRadius: 2,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    lineHeight: 1,
                    color: sevColor,
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  {sevIcon}
                </span>
                <div className="flex flex-col gap-1" style={{ minWidth: 0 }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      color: sevColor,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                    }}
                  >
                    {flag.severity}
                  </span>
                  <span
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--color-text-primary)',
                      lineHeight: 1.4,
                    }}
                  >
                    {flag.description}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Metric bar sub-component                                           */
/* ------------------------------------------------------------------ */

function MetricBar({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number;
  suffix: string;
}) {
  const barColor = qualityColor(value);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-primary)',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            color: barColor,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {value}
          {suffix}
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: 'var(--color-surface-overlay, rgba(255,255,255,0.06))',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.min(value, 100)}%`,
            background: barColor,
            borderRadius: 3,
            transition: 'width var(--transition-normal, 0.2s)',
          }}
        />
      </div>
    </div>
  );
}
