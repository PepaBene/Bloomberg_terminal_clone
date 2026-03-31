import type { CSSProperties } from 'react';

export type ComplianceStatus = 'Pass' | 'Warning' | 'Breach';

export interface ComplianceRule {
  rule: string;
  limit: string;
  current: string;
  status: ComplianceStatus;
}

export interface CompliancePanelProps {
  rules: ComplianceRule[];
  onAddRule?: () => void;
}

function statusIcon(status: ComplianceStatus): string {
  switch (status) {
    case 'Pass': return '✓';
    case 'Warning': return '⚠';
    case 'Breach': return '✗';
  }
}

function statusColor(status: ComplianceStatus): string {
  switch (status) {
    case 'Pass': return 'var(--color-signal-positive)';
    case 'Warning': return 'var(--color-signal-warning)';
    case 'Breach': return 'var(--color-signal-negative)';
  }
}

export function CompliancePanel({ rules, onAddRule }: CompliancePanelProps) {
  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 8px var(--space-2)',
    borderBottom: '1px solid var(--color-surface-border)',
  };

  const colHeaderStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '24px 1fr 90px 90px 80px',
    gap: 'var(--space-2)',
    padding: '4px 8px',
    borderBottom: '1px solid var(--color-surface-border)',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  const passCnt = rules.filter((r) => r.status === 'Pass').length;
  const warnCnt = rules.filter((r) => r.status === 'Warning').length;
  const breachCnt = rules.filter((r) => r.status === 'Breach').length;

  return (
    <div className="animate-in" style={rootStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          {[
            { label: 'Pass', count: passCnt, color: 'var(--color-signal-positive)' },
            { label: 'Warning', count: warnCnt, color: 'var(--color-signal-warning)' },
            { label: 'Breach', count: breachCnt, color: 'var(--color-signal-negative)' },
          ].map(({ label, count, color }) => (
            <span
              key={label}
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                color,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
                {count}
              </span>
              {label}
            </span>
          ))}
        </div>
        {onAddRule && (
          <button
            type="button"
            onClick={onAddRule}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              padding: '3px 10px',
              height: '24px',
              background: 'transparent',
              color: 'var(--color-accent-primary)',
              border: '1px solid var(--color-accent-primary)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            + Add Rule
          </button>
        )}
      </div>

      <div style={colHeaderStyle}>
        <span />
        <span>Rule</span>
        <span style={{ textAlign: 'right' }}>Limit</span>
        <span style={{ textAlign: 'right' }}>Current</span>
        <span style={{ textAlign: 'center' }}>Status</span>
      </div>

      {rules.map((rule, i) => {
        const color = statusColor(rule.status);
        const rowStyle: CSSProperties = {
          display: 'grid',
          gridTemplateColumns: '24px 1fr 90px 90px 80px',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: '6px 8px',
          borderBottom: '1px solid var(--color-surface-border)',
          borderLeft: rule.status === 'Breach' ? `3px solid ${color}` : rule.status === 'Warning' ? `3px solid ${color}` : '3px solid transparent',
          transition: 'background 0.1s',
        };

        return (
          <div
            key={i}
            style={rowStyle}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = 'transparent';
            }}
          >
            <span style={{ color, fontSize: '14px', lineHeight: 1, textAlign: 'center' }}>
              {statusIcon(rule.status)}
            </span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)' }}>
              {rule.rule}
            </span>
            <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textAlign: 'right' }}>
              {rule.limit}
            </span>
            <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--text-xs)', color, textAlign: 'right', fontWeight: rule.status !== 'Pass' ? 600 : 400 }}>
              {rule.current}
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color,
                border: `1px solid ${color}`,
                borderRadius: 'var(--radius-sm)',
                padding: '1px 6px',
                textAlign: 'center',
              }}
            >
              {rule.status}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default CompliancePanel;
