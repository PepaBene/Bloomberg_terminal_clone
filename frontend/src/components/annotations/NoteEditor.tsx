import { useState } from 'react';
import type { CSSProperties } from 'react';
import type { Annotation } from './useAnnotations';

const MAX_CHARS = 200;

const COLOR_SWATCHES = [
  { label: 'Accent', value: 'var(--color-accent-primary)' },
  { label: 'Positive', value: 'var(--color-signal-positive)' },
  { label: 'Warning', value: 'var(--color-signal-warning)' },
  { label: 'Chart', value: 'var(--color-chart-3)' },
];

interface NoteEditorProps {
  annotation?: Annotation;
  onSave: (note: string, color: string) => void;
  onCancel: () => void;
}

function NoteEditor({ annotation, onSave, onCancel }: NoteEditorProps) {
  const [note, setNote] = useState(annotation?.note ?? '');
  const [color, setColor] = useState(annotation?.color ?? (COLOR_SWATCHES[0]?.value ?? 'var(--color-accent-primary)'));

  const containerStyle: CSSProperties = {
    background: 'var(--color-surface-overlay)',
    border: '1px solid var(--color-surface-border-strong)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
    minWidth: 280,
    boxShadow: 'var(--shadow-float)',
  };

  const textareaStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    color: 'var(--color-text-primary)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    padding: 'var(--space-2)',
    resize: 'vertical',
    minHeight: 80,
    outline: 'none',
    lineHeight: 1.5,
    width: '100%',
    boxSizing: 'border-box',
    transition: 'border-color var(--transition-fast)',
  };

  const swatchRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
  };

  const swatchStyle = (swatchColor: string, active: boolean): CSSProperties => ({
    width: 16,
    height: 16,
    borderRadius: '50%',
    background: swatchColor,
    cursor: 'pointer',
    border: active ? '2px solid var(--color-text-primary)' : '2px solid transparent',
    outline: active ? '1px solid var(--color-surface-border-strong)' : 'none',
    flexShrink: 0,
    transition: 'border-color var(--transition-fast)',
  });

  const charCountStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontSize: 'var(--text-xs)',
    color: note.length > MAX_CHARS * 0.9
      ? 'var(--color-signal-warning)'
      : 'var(--color-text-tertiary)',
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
  };

  const actionsStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 'var(--space-2)',
  };

  const btnBase: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    fontWeight: 500,
    padding: 'var(--space-1) var(--space-3)',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid',
    cursor: 'pointer',
    transition: 'background var(--transition-fast)',
  };

  const cancelBtnStyle: CSSProperties = {
    ...btnBase,
    background: 'transparent',
    borderColor: 'var(--color-surface-border-strong)',
    color: 'var(--color-text-secondary)',
  };

  const saveBtnStyle: CSSProperties = {
    ...btnBase,
    background: 'var(--color-accent-primary)',
    borderColor: 'var(--color-accent-primary)',
    color: '#fff',
    opacity: note.trim().length === 0 || note.length > MAX_CHARS ? 0.5 : 1,
    cursor: note.trim().length === 0 || note.length > MAX_CHARS ? 'not-allowed' : 'pointer',
  };

  const labelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    marginRight: 'var(--space-2)',
  };

  return (
    <div style={containerStyle}>
      <textarea
        style={textareaStyle}
        value={note}
        onChange={e => setNote(e.target.value.slice(0, MAX_CHARS))}
        placeholder="Add a note..."
        autoFocus
        onFocus={e => (e.target.style.borderColor = 'var(--color-accent-primary)')}
        onBlur={e => (e.target.style.borderColor = 'var(--color-surface-border)')}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={swatchRowStyle}>
          <span style={labelStyle}>Color</span>
          {COLOR_SWATCHES.map(s => (
            <div
              key={s.value}
              style={swatchStyle(s.value, color === s.value)}
              onClick={() => setColor(s.value)}
              title={s.label}
            />
          ))}
        </div>
        <span style={charCountStyle}>{note.length}/{MAX_CHARS}</span>
      </div>
      <div style={actionsStyle}>
        <button style={cancelBtnStyle} onClick={onCancel}>Cancel</button>
        <button
          style={saveBtnStyle}
          onClick={() => {
            if (note.trim().length > 0 && note.length <= MAX_CHARS) {
              onSave(note.trim(), color);
            }
          }}
          disabled={note.trim().length === 0 || note.length > MAX_CHARS}
        >
          Save
        </button>
      </div>
    </div>
  );
}

export default NoteEditor;
