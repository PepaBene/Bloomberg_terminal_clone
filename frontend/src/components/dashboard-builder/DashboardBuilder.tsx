import React, { useState, useCallback, CSSProperties } from 'react';
import { useWorkspaceStore } from '@/stores/workspaceState';
import {
  PanelLayout,
  createDefaultLayout,
  compactLayout,
} from './gridEngine';
import { useDragResize } from './useDragResize';
import DragHandle from './DragHandle';
import ResizeHandle from './ResizeHandle';
import PanelCatalog from './PanelCatalog';
import { PanelRenderer } from './PanelRenderer';

const DEFAULT_COLS = 12;
const DEFAULT_ROWS = 12;
const CELL_H = 60; // pixels per row unit

interface PanelSlotProps {
  panel: PanelLayout;
  cols: number;
  onLayoutChange: (id: string, cell: import('./gridEngine').GridCell) => void;
  onRemove: (id: string) => void;
}

function PanelSlot({ panel, cols, onLayoutChange, onRemove }: PanelSlotProps) {
  const { dragHandleRef, resizeHandleRef, isDragging, isResizing, currentCell } =
    useDragResize(panel.id, panel.cell, onLayoutChange);

  const colW = `${(currentCell.w / cols) * 100}%`;
  const colOffset = `${(currentCell.x / cols) * 100}%`;
  const rowH = currentCell.h * CELL_H;
  const rowOffset = currentCell.y * CELL_H;

  const slotStyle: CSSProperties = {
    position: 'absolute',
    left: colOffset,
    top: rowOffset,
    width: colW,
    height: rowH,
    boxSizing: 'border-box',
    padding: 2,
    zIndex: isDragging || isResizing ? 100 : 1,
  };

  const innerStyle: CSSProperties = {
    width: '100%',
    height: '100%',
    background: 'var(--color-surface-base)',
    border: `1px solid ${isDragging || isResizing ? 'var(--color-accent-primary)' : 'var(--color-surface-border)'}`,
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    position: 'relative',
    transition: 'border-color var(--transition-fast)',
    opacity: isDragging ? 0.85 : 1,
    boxShadow: isDragging || isResizing ? 'var(--shadow-float)' : 'none',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: '0 var(--space-2)',
    height: 28,
    borderBottom: '1px solid var(--color-surface-border)',
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    color: 'var(--color-text-secondary)',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    flex: 1,
    userSelect: 'none',
  };

  const removeBtnStyle: CSSProperties = {
    background: 'none',
    border: 'none',
    color: 'var(--color-text-tertiary)',
    cursor: 'pointer',
    fontSize: 'var(--text-xs)',
    lineHeight: 1,
    padding: 'var(--space-1)',
    borderRadius: 'var(--radius-sm)',
  };

  const bodyStyle: CSSProperties = {
    flex: 1,
    overflow: 'auto',
    color: 'var(--color-text-tertiary)',
    fontSize: 'var(--text-xs)',
    fontFamily: 'var(--font-ui)',
    padding: 'var(--space-2)',
  };

  return (
    <div style={slotStyle} data-panel-id={panel.id}>
      <div style={innerStyle}>
        <div style={headerStyle}>
          <DragHandle
            onMouseDown={(e) => {
              // Forward to useDragResize's internal listener
              dragHandleRef.current?.dispatchEvent(
                new MouseEvent('mousedown', { clientX: e.clientX, clientY: e.clientY, bubbles: false })
              );
            }}
            // Attach ref via callback
          />
          {/* Hidden ref target for useDragResize */}
          <div ref={dragHandleRef} style={{ display: 'none' }} />
          <span style={titleStyle}>{panel.title}</span>
          <button
            style={removeBtnStyle}
            onClick={() => onRemove(panel.id)}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-signal-negative)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
            title="Remove panel"
          >
            ✕
          </button>
        </div>
        <div style={bodyStyle}>
          <PanelRenderer componentType={panel.componentType} />
        </div>
        <div ref={resizeHandleRef as React.RefObject<HTMLDivElement>} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <ResizeHandle
            onMouseDown={(e) => {
              resizeHandleRef.current?.dispatchEvent(
                new MouseEvent('mousedown', { clientX: e.clientX, clientY: e.clientY, bubbles: false })
              );
            }}
          />
        </div>
      </div>
    </div>
  );
}

interface DashboardBuilderProps {
  onSave?: (layout: PanelLayout[]) => void;
}

let nextPanelIdx = 6;

function DashboardBuilder({ onSave }: DashboardBuilderProps) {
  const addPanel = useWorkspaceStore((s) => s.addPanel);
  const [cols, setCols] = useState(DEFAULT_COLS);
  const [layout, setLayout] = useState<PanelLayout[]>(() => createDefaultLayout(DEFAULT_COLS));
  const [catalogOpen, setCatalogOpen] = useState(false);

  const handleLayoutChange = useCallback((id: string, cell: import('./gridEngine').GridCell) => {
    setLayout(prev => prev.map(p => p.id === id ? { ...p, cell } : p));
  }, []);

  const handleRemove = useCallback((id: string) => {
    setLayout(prev => prev.filter(p => p.id !== id));
  }, []);

  const handleAdd = useCallback((panelType: string) => {
    const newId = `panel-${nextPanelIdx++}`;
    const newPanel: PanelLayout = {
      id: newId,
      cell: { x: 0, y: 0, w: Math.floor(cols / 3), h: 4 },
      title: panelType.replace(/([A-Z])/g, ' $1').trim(),
      componentType: panelType,
    };
    setLayout(prev => [...prev, newPanel]);
    addPanel({ id: newId, type: panelType as import('@/types/workspace').PanelConfig['type'], position: { row: 0, col: 0, rowSpan: 4, colSpan: Math.floor(cols / 3) }, linkGroup: null, isExpanded: false, isDetached: false });
  }, [cols, addPanel]);

  const handleSave = () => {
    const compacted = compactLayout(layout);
    setLayout(compacted);
    onSave?.(compacted);
  };

  const handleReset = () => {
    setLayout(createDefaultLayout(cols));
  };

  const toolbarStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-surface-overlay)',
    borderBottom: '1px solid var(--color-surface-border)',
    flexShrink: 0,
  };

  const btnStyle = (variant: 'primary' | 'ghost' = 'ghost'): CSSProperties => ({
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    fontWeight: 500,
    padding: 'var(--space-1) var(--space-3)',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid',
    cursor: 'pointer',
    transition: 'background var(--transition-fast), color var(--transition-fast)',
    ...(variant === 'primary'
      ? {
          background: 'var(--color-accent-primary)',
          borderColor: 'var(--color-accent-primary)',
          color: 'var(--color-text-inverse)',
        }
      : {
          background: 'transparent',
          borderColor: 'var(--color-surface-border-strong)',
          color: 'var(--color-text-secondary)',
        }),
  });

  const labelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    marginLeft: 'var(--space-2)',
  };

  const selectStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-primary)',
    padding: '2px var(--space-2)',
    cursor: 'pointer',
  };

  const gridContainerStyle: CSSProperties = {
    flex: 1,
    position: 'relative',
    overflow: 'auto',
    background: 'var(--color-surface-void)',
    backgroundImage: `
      linear-gradient(var(--color-surface-border) 1px, transparent 1px),
      linear-gradient(90deg, var(--color-surface-border) 1px, transparent 1px)
    `,
    backgroundSize: `${100 / cols}% ${CELL_H}px`,
  };

  const gridInnerStyle: CSSProperties = {
    position: 'relative',
    minHeight: DEFAULT_ROWS * CELL_H,
  };

  const wrapperStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: 'var(--color-surface-void)',
  };

  return (
    <div style={wrapperStyle} className="animate-in">
      <div style={toolbarStyle}>
        <button style={btnStyle('primary')} onClick={() => setCatalogOpen(true)}>
          + Add Panel
        </button>
        <button style={btnStyle()} onClick={handleSave}>
          Save Layout
        </button>
        <button style={btnStyle()} onClick={handleReset}>
          Reset
        </button>
        <span style={labelStyle}>Columns:</span>
        <select
          style={selectStyle}
          value={cols}
          onChange={e => {
            const newCols = Number(e.target.value);
            setCols(newCols);
            setLayout(createDefaultLayout(newCols));
          }}
        >
          {[6, 8, 10, 12, 16, 24].map(n => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>

      <div style={gridContainerStyle} data-grid-container>
        <div style={gridInnerStyle}>
          {layout.map(panel => (
            <PanelSlot
              key={panel.id}
              panel={panel}
              cols={cols}
              onLayoutChange={handleLayoutChange}
              onRemove={handleRemove}
            />
          ))}
        </div>
      </div>

      <PanelCatalog
        open={catalogOpen}
        onClose={() => setCatalogOpen(false)}
        onAdd={handleAdd}
      />
    </div>
  );
}

export default DashboardBuilder;
