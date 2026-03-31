import { useState, useMemo } from 'react';
import type { CSSProperties } from 'react';
import { useAnnotations, Annotation } from './useAnnotations';
import NoteEditor from './NoteEditor';

interface NotesPanelProps {
  open: boolean;
  onClose: () => void;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function NotesPanel({ open, onClose }: NotesPanelProps) {
  const { annotations, update, remove } = useAnnotations();
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!search.trim()) return annotations;
    const q = search.toLowerCase();
    return annotations.filter(a =>
      a.note.toLowerCase().includes(q) || a.targetId.toLowerCase().includes(q),
    );
  }, [annotations, search]);

  // Group by targetId
  const grouped = useMemo(() => {
    const map = new Map<string, Annotation[]>();
    for (const a of filtered) {
      const arr = map.get(a.targetId) ?? [];
      arr.push(a);
      map.set(a.targetId, arr);
    }
    return map;
  }, [filtered]);

  const backdropStyle: CSSProperties = {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.6)',
    zIndex: 900,
    opacity: open ? 1 : 0,
    pointerEvents: open ? 'auto' : 'none',
    transition: 'opacity var(--transition-normal)',
  };

  const panelStyle: CSSProperties = {
    position: 'fixed', top: 0, right: 0, bottom: 0,
    width: 380,
    background: 'var(--color-surface-base)',
    borderLeft: '1px solid var(--color-surface-border-strong)',
    zIndex: 901,
    display: 'flex', flexDirection: 'column',
    transform: open ? 'translateX(0)' : 'translateX(100%)',
    transition: 'transform var(--transition-normal)',
    boxShadow: 'var(--shadow-float)',
  };

  const headerStyle: CSSProperties = {
    padding: 'var(--space-4)',
    borderBottom: '1px solid var(--color-surface-border)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', fontWeight: 600,
    color: 'var(--color-text-primary)', margin: 0,
  };

  const closeBtn: CSSProperties = {
    background: 'none', border: 'none',
    color: 'var(--color-text-tertiary)', cursor: 'pointer',
    fontSize: 'var(--text-lg)', lineHeight: 1, padding: 'var(--space-1)',
    borderRadius: 'var(--radius-sm)',
  };

  const searchStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-primary)',
    padding: 'var(--space-2) var(--space-3)',
    outline: 'none', width: '100%', boxSizing: 'border-box',
  };

  const searchWrap: CSSProperties = {
    padding: 'var(--space-3)',
    borderBottom: '1px solid var(--color-surface-border)',
    flexShrink: 0,
  };

  const scrollArea: CSSProperties = {
    flex: 1, overflowY: 'auto', padding: 'var(--space-3)',
  };

  const emptyStyle: CSSProperties = {
    textAlign: 'center', padding: 'var(--space-8)',
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
    color: 'var(--color-text-tertiary)',
  };

  const groupLabelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600,
    color: 'var(--color-text-tertiary)', textTransform: 'uppercase',
    letterSpacing: '0.08em', margin: '0 0 var(--space-2)',
    padding: 'var(--space-2) 0',
  };

  const noteCardStyle = (color: string): CSSProperties => ({
    borderLeft: `3px solid ${color}`,
    background: 'var(--color-surface-overlay)',
    borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
    padding: 'var(--space-2) var(--space-3)',
    marginBottom: 'var(--space-2)',
  });

  const noteTextStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
    color: 'var(--color-text-primary)', lineHeight: 1.5, margin: '0 0 var(--space-1)',
    whiteSpace: 'pre-wrap',
  };

  const metaRowStyle: CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  };

  const timestampStyle: CSSProperties = {
    fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)', fontVariantNumeric: 'tabular-nums',
  };

  const actionBtnStyle: CSSProperties = {
    background: 'none', border: 'none', cursor: 'pointer',
    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)', padding: '0 var(--space-1)',
    borderRadius: 'var(--radius-sm)',
    transition: 'color var(--transition-fast)',
  };

  return (
    <>
      <div style={backdropStyle} onClick={onClose} />
      <div style={panelStyle}>
        <div style={headerStyle}>
          <p style={titleStyle}>Annotations</p>
          <button style={closeBtn} onClick={onClose}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
          >✕</button>
        </div>

        <div style={searchWrap}>
          <input
            style={searchStyle}
            placeholder="Search notes..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            onFocus={e => (e.target.style.borderColor = 'var(--color-accent-primary)')}
            onBlur={e => (e.target.style.borderColor = 'var(--color-surface-border)')}
          />
        </div>

        <div style={scrollArea}>
          {grouped.size === 0 && (
            <div style={emptyStyle}>
              {search ? 'No annotations match your search.' : 'No annotations yet.'}
            </div>
          )}
          {Array.from(grouped.entries()).map(([targetId, notes]) => (
            <div key={targetId}>
              <p style={groupLabelStyle}>{targetId}</p>
              {notes.map(ann => (
                <div key={ann.id}>
                  {editingId === ann.id ? (
                    <div style={{ marginBottom: 'var(--space-2)' }}>
                      <NoteEditor
                        annotation={ann}
                        onSave={(note, color) => {
                          update(ann.id, { note, color });
                          setEditingId(null);
                        }}
                        onCancel={() => setEditingId(null)}
                      />
                    </div>
                  ) : (
                    <div style={noteCardStyle(ann.color)}>
                      <p style={noteTextStyle}>{ann.note}</p>
                      <div style={metaRowStyle}>
                        <span style={timestampStyle}>{formatTimestamp(ann.createdAt)}</span>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button
                            style={actionBtnStyle}
                            onClick={() => setEditingId(ann.id)}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-accent-primary)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
                          >Edit</button>
                          <button
                            style={actionBtnStyle}
                            onClick={() => remove(ann.id)}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-signal-negative)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
                          >Delete</button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default NotesPanel;
