import { useState, useCallback, type ReactNode } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FilterGroupBracketProps {
  type: 'AND' | 'OR';
  children: ReactNode;
  onToggle?: (type: 'AND' | 'OR') => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function FilterGroupBracket({ type, children, onToggle }: FilterGroupBracketProps) {
  const [groupType, setGroupType] = useState(type);

  const handleToggle = useCallback(() => {
    const next = groupType === 'AND' ? 'OR' : 'AND';
    setGroupType(next);
    onToggle?.(next);
  }, [groupType, onToggle]);

  const bracketColor =
    groupType === 'AND'
      ? 'var(--color-accent-primary)'
      : 'var(--color-signal-warning)';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'stretch',
        gap: 0,
        position: 'relative',
      }}
    >
      {/* Left bracket + label */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          width: 36,
          flexShrink: 0,
        }}
      >
        {/* Bracket line */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 4,
            bottom: 4,
            width: 3,
            background: bracketColor,
            borderRadius: 2,
          }}
        />
        {/* Top cap */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 4,
            width: 10,
            height: 3,
            background: bracketColor,
            borderRadius: '2px 2px 0 0',
          }}
        />
        {/* Bottom cap */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            bottom: 4,
            width: 10,
            height: 3,
            background: bracketColor,
            borderRadius: '0 0 2px 2px',
          }}
        />

        {/* Toggle button */}
        <button
          type="button"
          onClick={handleToggle}
          style={{
            background: bracketColor,
            color: 'var(--color-surface-base)',
            border: 'none',
            borderRadius: 3,
            padding: '2px 4px',
            fontFamily: 'var(--font-ui)',
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.04em',
            cursor: 'pointer',
            lineHeight: 1,
            marginLeft: 6,
            zIndex: 1,
            userSelect: 'none',
          }}
          title={`Toggle to ${groupType === 'AND' ? 'OR' : 'AND'}`}
        >
          {groupType}
        </button>
      </div>

      {/* Children */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {children}
      </div>
    </div>
  );
}
