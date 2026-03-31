import { useState, useCallback } from 'react';
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
  CRITICAL: 'var(--signal-negative)',
  HIGH: 'var(--signal-warning)',
  MEDIUM: 'var(--signal-highlight)',
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
  if (pct >= 80) return 'var(--quality-5)';
  if (pct >= 60) return 'var(--quality-4)';
  if (pct >= 40) return 'var(--quality-3)';
  if (pct >= 20) return 'var(--quality-2)';
  return 'var(--quality-1)';
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
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null);

  const toggleFlag = useCallback((id: string) => {
    setExpandedFlag((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-4)',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-4)',
      }}
    >
      {/* Header: gauge + classification */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <GaugeChart value={score} max={100} label="Governance" size={100} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              fontVariantNumeric: 'tabular-nums',
              color: scoreColor,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '2px var(--space-2)',
              background: `color-mix(in srgb, ${scoreColor} 15%, transparent)`,
              borderRadius: 'var(--radius-sm)',
              whiteSpace: 'nowrap',
              alignSelf: 'flex-start',
            }}
          >
            {classification}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {/* Board Independence */}
        <MetricBar
          label="Board Independence"
          value={boardIndependence}
          suffix="%"
        />

        {/* CEO / Chair Separation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-primary)',
            }}
          >
            CEO / Chair Separation
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontWeight: 500,
              fontVariantNumeric: 'tabular-nums',
              color: ceoIsChair
                ? 'var(--signal-negative)'
                : 'var(--signal-positive)',
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Red Flags ({redFlags.length})
          </span>
          {redFlags.map((flag) => {
            const sevColor =
              SEVERITY_COLORS[flag.severity] ?? 'var(--signal-neutral)';
            const sevIcon = SEVERITY_ICONS[flag.severity] ?? '\u25CF';
            const isExpanded = expandedFlag === flag.id;

            return (
              <button
                type="button"
                key={flag.id}
                onClick={() => toggleFlag(flag.id)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-2)',
                  padding: 'var(--space-1) var(--space-2)',
                  background: 'var(--surface-raised)',
                  borderLeft: `3px solid ${sevColor}`,
                  borderTop: 'none',
                  borderRight: 'none',
                  borderBottom: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  width: '100%',
                  textAlign: 'left',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--surface-overlay)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--surface-raised)';
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', minWidth: 0, flex: 1 }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      fontVariantNumeric: 'tabular-nums',
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
                      color: 'var(--text-primary)',
                      lineHeight: 1.4,
                      maxHeight: isExpanded ? '200px' : '1.4em',
                      overflow: 'hidden',
                      transition: 'max-height var(--transition-normal)',
                    }}
                  >
                    {flag.description}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 10,
                    color: 'var(--text-tertiary)',
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  {isExpanded ? '\u25B2' : '\u25BC'}
                </span>
              </button>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-primary)',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontVariantNumeric: 'tabular-nums',
            color: barColor,
          }}
        >
          {value}
          {suffix}
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 'var(--radius-sm)',
          background: 'var(--surface-overlay)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.min(value, 100)}%`,
            background: barColor,
            borderRadius: 'var(--radius-sm)',
            transition: 'width var(--transition-normal)',
          }}
        />
      </div>
    </div>
  );
}
