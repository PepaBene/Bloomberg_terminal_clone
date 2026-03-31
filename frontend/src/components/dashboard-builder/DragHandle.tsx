import React, { useState, CSSProperties } from 'react';

interface DragHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
  className?: string;
}

const DOT_SIZE = 3;
const DOT_GAP = 3;

const dotStyle: CSSProperties = {
  width: DOT_SIZE,
  height: DOT_SIZE,
  borderRadius: '50%',
  backgroundColor: 'currentColor',
  flexShrink: 0,
};

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: `repeat(2, ${DOT_SIZE}px)`,
  gridTemplateRows: `repeat(3, ${DOT_SIZE}px)`,
  gap: DOT_GAP,
  padding: 'var(--space-1)',
  lineHeight: 0,
};

function DragHandle({ onMouseDown, className }: DragHandleProps) {
  const [hovered, setHovered] = useState(false);
  const [pressing, setPressing] = useState(false);

  const wrapperStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: hovered
      ? 'var(--color-text-secondary)'
      : 'var(--color-text-tertiary)',
    cursor: pressing ? 'grabbing' : 'grab',
    borderRadius: 'var(--radius-sm)',
    transition: 'color var(--transition-fast)',
    userSelect: 'none',
    flexShrink: 0,
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setPressing(true);
    onMouseDown(e);
  };

  return (
    <div
      style={wrapperStyle}
      className={className}
      onMouseDown={handleMouseDown}
      onMouseUp={() => setPressing(false)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setPressing(false); }}
      title="Drag to move"
    >
      <div style={gridStyle}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={dotStyle} />
        ))}
      </div>
    </div>
  );
}

export default DragHandle;
