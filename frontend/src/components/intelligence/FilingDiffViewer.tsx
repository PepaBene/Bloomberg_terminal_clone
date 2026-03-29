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
  add: 'rgba(45, 184, 125, 0.10)',
  remove: 'rgba(224, 82, 82, 0.10)',
  modify: 'rgba(212, 168, 67, 0.10)',
};

const CHANGE_BORDER: Record<DiffChange['type'], string> = {
  add: 'var(--color-signal-positive)',
  remove: 'var(--color-signal-negative)',
  modify: 'var(--color-signal-highlight)',
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
      className={clsx('flex flex-col', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
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
                gap: 8,
                padding: '8px 12px',
                background: 'var(--color-surface-raised)',
                borderBottom: '1px solid var(--color-surface-border)',
                borderTop: 'none',
                borderLeft: 'none',
                borderRight: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                color: 'var(--color-text-primary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                textAlign: 'left',
              }}
            >
              <span className="flex items-center gap-2">
                <span style={{ color: 'var(--color-text-tertiary)' }}>
                  {isExpanded ? '\u25BC' : '\u25B6'}
                </span>
                {section.name}
              </span>
              {changeCount > 0 && (
                <span
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-signal-warning)',
                    fontWeight: 500,
                  }}
                >
                  {changeCount} change{changeCount !== 1 ? 's' : ''}
                </span>
              )}
            </button>

            {/* Content */}
            {isExpanded && (
              <div style={{ padding: 0 }}>
                {mode === 'side-by-side' ? (
                  <SideBySideView section={section} />
                ) : (
                  <UnifiedView section={section} />
                )}
              </div>
            )}
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
        <div style={{ gridColumn: '1 / -1', padding: '8px 12px' }}>
          <div
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: 6,
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
          borderLeft: '1px solid var(--color-surface-border)',
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
    <div style={{ padding: '8px 12px' }}>
      {section.changes.length === 0 ? (
        <div
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-tertiary)',
            padding: '12px 0',
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
        gap: 8,
        padding: '6px 8px',
        marginBottom: 4,
        background: CHANGE_BG[change.type],
        borderLeft: `3px solid ${CHANGE_BORDER[change.type]}`,
        borderRadius: 2,
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xs)',
          fontWeight: 500,
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
          color: 'var(--color-text-primary)',
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
  color: 'var(--color-text-tertiary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  padding: '6px 12px',
  background: 'var(--color-surface-raised)',
  borderBottom: '1px solid var(--color-surface-border)',
};

const lineStyle: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  padding: '2px 12px',
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-xs)',
  color: 'var(--color-text-primary)',
  lineHeight: 1.6,
  minHeight: 22,
};

const lineNumStyle: React.CSSProperties = {
  color: 'var(--color-text-tertiary)',
  fontVariantNumeric: 'tabular-nums',
  minWidth: 28,
  textAlign: 'right',
  flexShrink: 0,
  userSelect: 'none',
};
