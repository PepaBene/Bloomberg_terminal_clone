import type { CSSProperties } from 'react';

export interface AnomalyData {
  id: string;
  ticker: string;
  type: string;
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  detectedAt: string;
  metric?: string;
  value?: number;
  expected?: number;
}

export interface AnomalyCardProps {
  anomaly: AnomalyData;
  onInvestigate?: (id: string) => void;
}

const SEVERITY_BORDER: Record<string, string> = {
  HIGH: 'var(--color-signal-negative)',
  MEDIUM: 'var(--color-signal-warning)',
  LOW: 'var(--color-signal-neutral)',
};

const SEVERITY_LABEL_COLOR: Record<string, string> = {
  HIGH: 'var(--color-signal-negative)',
  MEDIUM: 'var(--color-signal-warning)',
  LOW: 'var(--color-signal-neutral)',
};

function fmtTimeAgo(dateStr: string): string {
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function AnomalyCard({ anomaly, onInvestigate }: AnomalyCardProps) {
  const borderColor = SEVERITY_BORDER[anomaly.severity] ?? 'var(--color-surface-border-strong)';
  const labelColor = SEVERITY_LABEL_COLOR[anomaly.severity] ?? 'var(--color-text-secondary)';

  const hasDeviation = anomaly.value != null && anomaly.expected != null;
  const deviation = hasDeviation ? ((anomaly.value! - anomaly.expected!) / Math.abs(anomaly.expected!)) * 100 : null;

  const cardStyle: CSSProperties = {
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderLeft: `3px solid ${borderColor}`,
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  return (
    <div className="animate-in" style={cardStyle}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            color: 'var(--color-accent-primary)',
            background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {anomaly.ticker}
          </span>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: labelColor,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            {anomaly.severity}
          </span>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            background: 'var(--color-surface-raised)',
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {anomaly.type}
          </span>
        </div>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
          {fmtTimeAgo(anomaly.detectedAt)}
        </span>
      </div>

      {/* Description */}
      <p style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text-secondary)',
        margin: 0,
        lineHeight: 1.5,
      }}>
        {anomaly.description}
      </p>

      {/* Metric deviation */}
      {hasDeviation && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          background: 'var(--color-surface-raised)',
          borderRadius: 'var(--radius-sm)',
          padding: 'var(--space-2) var(--space-3)',
        }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', minWidth: 80 }}>
            {anomaly.metric}
          </span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-primary)' }}>
            {anomaly.value?.toFixed(2)}
          </span>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>vs</span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)' }}>
            {anomaly.expected?.toFixed(2)} expected
          </span>
          {deviation != null && (
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              fontVariantNumeric: 'tabular-nums',
              color: deviation > 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)',
              marginLeft: 'auto',
            }}>
              {deviation >= 0 ? '+' : ''}{deviation.toFixed(1)}%
            </span>
          )}
        </div>
      )}

      {onInvestigate && (
        <button
          type="button"
          onClick={() => onInvestigate(anomaly.id)}
          style={{
            alignSelf: 'flex-start',
            background: 'none',
            border: `1px solid ${borderColor}`,
            borderRadius: 'var(--radius-sm)',
            padding: '3px 10px',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: labelColor,
            cursor: 'pointer',
          }}
        >
          Investigate →
        </button>
      )}
    </div>
  );
}

export default AnomalyCard;
