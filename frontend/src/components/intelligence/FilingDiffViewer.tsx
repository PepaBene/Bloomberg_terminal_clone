import { useState, useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DiffChange {
  type: 'add' | 'remove' | 'modify';
  text: string;
}

export interface DiffSection {
  name: string;
  prior: string;
  current: string;
  changes: DiffChange[];
}

export interface FilingDiffViewerProps {
  sections: DiffSection[];
  /** 'side-by-side' or 'unified' (default: 'side-by-side') */
  mode?: 'side-by-side' | 'unified';
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const CHANGE_BG: Record<DiffChange['type'], string> = {
  add: 'color-mix(in srgb, var(--signal-positive) 8%, transparent)',
  remove: 'color-mix(in srgb, var(--signal-negative) 8%, transparent)',
  modify: 'color-mix(in srgb, var(--signal-warning) 8%, transparent)',
};

const CHANGE_BORDER: Record<DiffChange['type'], string> = {
  add: 'var(--signal-positive)',
  remove: 'var(--signal-negative)',
  modify: 'var(--signal-warning)',
};

const CHANGE_LABEL: Record<DiffChange['type'], string> = {
  add: 'ADD',
  remove: 'DEL',
  modify: 'MOD',
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function FilingDiffViewer({
  sections,
  mode = 'side-by-side',
  className,
}: FilingDiffViewerProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>(
    sections[0]?.name ?? null,
  );

  const toggleSection = useCallback((name: string) => {
    setExpandedSection((prev) => (prev === name ? null : name));
  }, []);

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        overflow: 'hidden',
      }}
    >
      {sections.map((section) => {
        const isExpanded = expandedSection === section.name;
        const changeCount = section.changes.length;

        return (
          <div key={section.name}>
            {/* Sticky section header */}
            <button
              type="button"
              onClick={() => toggleSection(section.name)}
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 2,
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--surface-raised)',
                borderBottom: '1px solid var(--surface-border)',
                borderTop: 'none',
                borderLeft: 'none',
                borderRight: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-md)',
                fontWeight: 600,
                color: 'var(--text-primary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                textAlign: 'left',
                transition: 'background var(--transition-fast)',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>
                  {isExpanded ? '\u25BC' : '\u25B6'}
                </span>
                {section.name}
              </span>
              {changeCount > 0 && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--signal-warning)',
                    fontWeight: 500,
                  }}
                >
                  {changeCount} change{changeCount !== 1 ? 's' : ''}
                </span>
              )}
            </button>

            {/* Content — expand/collapse with smooth transition */}
            <div
              style={{
                overflow: 'hidden',
                maxHeight: isExpanded ? '4000px' : '0px',
                transition: 'max-height var(--transition-normal)',
              }}
            >
              <div>
                {mode === 'side-by-side' ? (
                  <SideBySideView section={section} />
                ) : (
                  <UnifiedView section={section} />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Side-by-side view                                                  */
/* ------------------------------------------------------------------ */

function SideBySideView({ section }: { section: DiffSection }) {
  const priorLines = section.prior.split('\n');
  const currentLines = section.current.split('\n');
  const maxLines = Math.max(priorLines.length, currentLines.length);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
      {/* Column headers */}
      <div style={columnHeaderStyle}>Prior Year</div>
      <div style={columnHeaderStyle}>Current Year</div>

      {/* Lines */}
      {Array.from({ length: maxLines }, (_, i) => (
        <SideBySideRow
          key={i}
          lineNum={i + 1}
          prior={priorLines[i]}
          current={currentLines[i]}
        />
      ))}

      {/* Changes summary */}
      {section.changes.length > 0 && (
        <div style={{ gridColumn: '1 / -1', padding: 'var(--space-2) var(--space-3)' }}>
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: 'var(--space-1)',
            }}
          >
            Detected Changes
          </div>
          {section.changes.map((c, idx) => (
            <ChangeRow key={idx} change={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function SideBySideRow({
  lineNum,
  prior,
  current,
}: {
  lineNum: number;
  prior?: string;
  current?: string;
}) {
  return (
    <>
      <div style={lineStyle}>
        <span style={lineNumStyle}>{prior != null ? lineNum : ''}</span>
        <span style={{ whiteSpace: 'pre-wrap' }}>{prior ?? ''}</span>
      </div>
      <div
        style={{
          ...lineStyle,
          borderLeft: '1px solid var(--surface-border)',
        }}
      >
        <span style={lineNumStyle}>{current != null ? lineNum : ''}</span>
        <span style={{ whiteSpace: 'pre-wrap' }}>{current ?? ''}</span>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Unified view                                                       */
/* ------------------------------------------------------------------ */

function UnifiedView({ section }: { section: DiffSection }) {
  return (
    <div style={{ padding: 'var(--space-2) var(--space-3)' }}>
      {section.changes.length === 0 ? (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-tertiary)',
            padding: 'var(--space-3) 0',
          }}
        >
          No changes detected in this section.
        </div>
      ) : (
        section.changes.map((c, idx) => <ChangeRow key={idx} change={c} />)
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared sub-components                                              */
/* ------------------------------------------------------------------ */

function ChangeRow({ change }: { change: DiffChange }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--space-2)',
        padding: 'var(--space-1) var(--space-2)',
        marginBottom: 'var(--space-1)',
        background: CHANGE_BG[change.type],
        borderLeft: `3px solid ${CHANGE_BORDER[change.type]}`,
        borderRadius: 'var(--radius-sm)',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
          fontVariantNumeric: 'tabular-nums',
          color: CHANGE_BORDER[change.type],
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          flexShrink: 0,
          minWidth: 28,
        }}
      >
        {CHANGE_LABEL[change.type]}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-primary)',
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
        }}
      >
        {change.text}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const columnHeaderStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  fontWeight: 600,
  color: 'var(--text-tertiary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  padding: 'var(--space-1) var(--space-3)',
  background: 'var(--surface-raised)',
  borderBottom: '1px solid var(--surface-border)',
};

const lineStyle: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--space-2)',
  padding: '2px var(--space-3)',
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-xs)',
  color: 'var(--text-primary)',
  lineHeight: 1.6,
  minHeight: 22,
};

const lineNumStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  color: 'var(--text-tertiary)',
  fontVariantNumeric: 'tabular-nums',
  minWidth: 28,
  textAlign: 'right',
  flexShrink: 0,
  userSelect: 'none',
};
