import { useState, useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface AlertRuleCondition {
  metric: string;
  operator: '>' | '<' | '=' | '>=' | '<=';
  threshold: number;
}

export interface AlertRuleConfig {
  id?: string;
  entityScope: string;
  alertType: string;
  conditions: AlertRuleCondition[];
  isEnabled: boolean;
  quietHoursStart?: string;
  quietHoursEnd?: string;
}

export interface AlertRuleEditorProps {
  rule?: AlertRuleConfig;
  onSave: (rule: AlertRuleConfig) => void;
  onCancel: () => void;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ALERT_TYPES = [
  'PRICE_CHANGE',
  'FILING_DETECTED',
  'EARNINGS_SURPRISE',
  'SCORE_CHANGE',
  'INSIDER_ACTIVITY',
  'RATING_CHANGE',
];

const OPERATORS: AlertRuleCondition['operator'][] = ['>', '<', '=', '>=', '<='];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AlertRuleEditor({
  rule,
  onSave,
  onCancel,
  className,
}: AlertRuleEditorProps) {
  const [entityScope, setEntityScope] = useState(rule?.entityScope ?? '');
  const [alertType, setAlertType] = useState(rule?.alertType ?? ALERT_TYPES[0] ?? '');
  const [conditions, setConditions] = useState<AlertRuleCondition[]>(
    rule?.conditions ?? [{ metric: '', operator: '>', threshold: 0 }],
  );
  const [isEnabled, setIsEnabled] = useState(rule?.isEnabled ?? true);
  const [quietStart, setQuietStart] = useState(rule?.quietHoursStart ?? '');
  const [quietEnd, setQuietEnd] = useState(rule?.quietHoursEnd ?? '');

  const handleAddCondition = useCallback(() => {
    setConditions((prev) => [...prev, { metric: '', operator: '>', threshold: 0 }]);
  }, []);

  const handleRemoveCondition = useCallback((idx: number) => {
    setConditions((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleConditionChange = useCallback(
    (idx: number, field: keyof AlertRuleCondition, value: string | number) => {
      setConditions((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c)),
      );
    },
    [],
  );

  const handleSave = useCallback(() => {
    onSave({
      id: rule?.id,
      entityScope,
      alertType,
      conditions,
      isEnabled,
      quietHoursStart: quietStart || undefined,
      quietHoursEnd: quietEnd || undefined,
    });
  }, [rule, entityScope, alertType, conditions, isEnabled, quietStart, quietEnd, onSave]);

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
      {/* Title */}
      <div className="flex items-center justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {rule?.id ? 'Edit Alert Rule' : 'New Alert Rule'}
        </span>
        {/* Enable toggle */}
        <button
          type="button"
          onClick={() => setIsEnabled((v) => !v)}
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: isEnabled ? 'var(--color-signal-positive)' : 'var(--color-text-tertiary)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '2px 8px',
            border: `1px solid ${isEnabled ? 'var(--color-signal-positive)' : 'var(--color-surface-border)'}`,
            borderRadius: '9999px',
            background: 'transparent',
            cursor: 'pointer',
          }}
        >
          {isEnabled ? 'ENABLED' : 'DISABLED'}
        </button>
      </div>

      {/* Entity selector */}
      <FormField label="Entity Scope">
        <input
          type="text"
          value={entityScope}
          onChange={(e) => setEntityScope(e.target.value)}
          placeholder="e.g. AAPL, MSFT or * for all"
          style={inputStyle}
        />
      </FormField>

      {/* Alert type */}
      <FormField label="Alert Type">
        <select
          value={alertType}
          onChange={(e) => setAlertType(e.target.value)}
          style={inputStyle}
        >
          {ALERT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </FormField>

      {/* Conditions */}
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
          Conditions
        </span>
        {conditions.map((cond, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 8px',
              background: 'var(--color-surface-raised)',
              borderRadius: 4,
              border: '1px solid var(--color-surface-border)',
            }}
          >
            <input
              type="text"
              value={cond.metric}
              onChange={(e) => handleConditionChange(idx, 'metric', e.target.value)}
              placeholder="Metric"
              style={{ ...inputStyle, flex: 2 }}
            />
            <select
              value={cond.operator}
              onChange={(e) =>
                handleConditionChange(idx, 'operator', e.target.value)
              }
              style={{ ...inputStyle, width: 60 }}
            >
              {OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={cond.threshold}
              onChange={(e) =>
                handleConditionChange(idx, 'threshold', parseFloat(e.target.value) || 0)
              }
              style={{ ...inputStyle, width: 80, fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}
            />
            <button
              type="button"
              onClick={() => handleRemoveCondition(idx)}
              style={removeButtonStyle}
              title="Remove condition"
              aria-label={`Remove condition ${idx + 1}`}
            >
              {'\u2715'}
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={handleAddCondition}
          style={addButtonStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--color-surface-overlay)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--color-surface-raised)';
          }}
        >
          + Add Condition
        </button>
      </div>

      {/* Quiet hours */}
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
          Quiet Hours
        </span>
        <div className="flex items-center gap-2">
          <input
            type="time"
            value={quietStart}
            onChange={(e) => setQuietStart(e.target.value)}
            style={{ ...inputStyle, width: 120 }}
          />
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            to
          </span>
          <input
            type="time"
            value={quietEnd}
            onChange={(e) => setQuietEnd(e.target.value)}
            style={{ ...inputStyle, width: 120 }}
          />
        </div>
      </div>

      {/* Preview */}
      <div
        style={{
          padding: '8px 12px',
          background: 'var(--color-surface-raised)',
          border: '1px solid var(--color-surface-border)',
          borderRadius: 4,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Preview
        </span>
        <p
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-primary)',
            margin: '4px 0 0',
            lineHeight: 1.4,
          }}
        >
          Alert on{' '}
          <strong>{entityScope || '...'}</strong>{' '}
          when{' '}
          <strong>{alertType.replace(/_/g, ' ').toLowerCase()}</strong>
          {conditions.length > 0 && conditions[0]?.metric && (
            <>
              {' '}and{' '}
              <strong>{conditions[0].metric}</strong>{' '}
              {conditions[0].operator}{' '}
              <strong>{conditions[0].threshold}</strong>
            </>
          )}
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: 'var(--color-text-tertiary)',
            background: 'transparent',
            border: '1px solid var(--color-surface-border)',
            borderRadius: 4,
            padding: '6px 16px',
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            background: 'var(--color-accent-primary)',
            border: 'none',
            borderRadius: 4,
            padding: '6px 16px',
            cursor: 'pointer',
          }}
        >
          Save Rule
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
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
        {label}
      </span>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const inputStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: 3,
  padding: '4px 8px',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  outline: 'none',
};

const removeButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--color-text-tertiary)',
  cursor: 'pointer',
  fontSize: 14,
  lineHeight: 1,
  padding: '2px 4px',
  flexShrink: 0,
};

const addButtonStyle: React.CSSProperties = {
  alignSelf: 'flex-start',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-accent-primary)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: 4,
  padding: '6px 14px',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  fontWeight: 500,
  cursor: 'pointer',
  letterSpacing: '0.02em',
  transition: 'background var(--transition-fast, 0.1s)',
};
