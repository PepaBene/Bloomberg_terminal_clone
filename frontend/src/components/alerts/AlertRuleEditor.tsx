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
      {/* Title + toggle */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--text-primary)',
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
            width: 36,
            height: 20,
            borderRadius: 10,
            background: isEnabled
              ? 'var(--accent-primary)'
              : 'var(--surface-border-strong)',
            border: 'none',
            position: 'relative',
            cursor: 'pointer',
            padding: 0,
            transition: 'background var(--transition-fast)',
          }}
          title={isEnabled ? 'Enabled' : 'Disabled'}
          aria-label={`Toggle rule ${isEnabled ? 'off' : 'on'}`}
        >
          <span
            style={{
              position: 'absolute',
              top: 2,
              left: isEnabled ? 18 : 2,
              width: 16,
              height: 16,
              borderRadius: '50%',
              background: 'var(--text-primary)',
              transition: 'left var(--transition-fast)',
            }}
          />
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
          Conditions
        </span>
        {conditions.map((cond, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              padding: 'var(--space-1) var(--space-2)',
              background: 'var(--surface-raised)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--surface-border)',
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
              style={{
                ...inputStyle,
                width: 80,
                fontFamily: 'var(--font-data)',
                fontVariantNumeric: 'tabular-nums',
              }}
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
            e.currentTarget.style.background = 'var(--surface-overlay)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--surface-raised)';
          }}
        >
          + Add Condition
        </button>
      </div>

      {/* Quiet hours */}
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
          Quiet Hours
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <input
            type="time"
            value={quietStart}
            onChange={(e) => setQuietStart(e.target.value)}
            style={{
              ...inputStyle,
              width: 120,
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
            }}
          />
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-tertiary)',
            }}
          >
            to
          </span>
          <input
            type="time"
            value={quietEnd}
            onChange={(e) => setQuietEnd(e.target.value)}
            style={{
              ...inputStyle,
              width: 120,
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
            }}
          />
        </div>
      </div>

      {/* Preview */}
      <div
        style={{
          padding: 'var(--space-2) var(--space-3)',
          background: 'var(--surface-base)',
          border: '1px dashed var(--surface-border)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-tertiary)',
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
            color: 'var(--text-primary)',
            margin: 'var(--space-1) 0 0',
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
        <button
          type="button"
          onClick={onCancel}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: 'var(--text-tertiary)',
            background: 'transparent',
            border: '1px solid var(--surface-border)',
            borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-1) var(--space-4)',
            cursor: 'pointer',
            transition: 'background var(--transition-fast)',
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
            color: 'var(--text-primary)',
            background: 'var(--accent-primary)',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-1) var(--space-4)',
            cursor: 'pointer',
            transition: 'background var(--transition-fast)',
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
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
  background: 'var(--surface-raised)',
  color: 'var(--text-primary)',
  border: '1px solid var(--surface-border)',
  borderRadius: 'var(--radius-sm)',
  padding: 'var(--space-1) var(--space-2)',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  outline: 'none',
  transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
};

const removeButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
  fontSize: 14,
  lineHeight: 1,
  padding: '2px var(--space-1)',
  flexShrink: 0,
  transition: 'color var(--transition-fast)',
};

const addButtonStyle: React.CSSProperties = {
  alignSelf: 'flex-start',
  background: 'var(--surface-raised)',
  color: 'var(--accent-primary)',
  border: '1px solid var(--surface-border)',
  borderRadius: 'var(--radius-sm)',
  padding: 'var(--space-1) var(--space-3)',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  fontWeight: 500,
  cursor: 'pointer',
  letterSpacing: '0.02em',
  transition: 'background var(--transition-fast)',
};
