import React, { useState, CSSProperties } from 'react';

interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
}

function ResizeHandle({ onMouseDown }: ResizeHandleProps) {
  const [hovered, setHovered] = useState(false);

  const containerStyle: CSSProperties = {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 16,
    height: 16,
    cursor: 'nwse-resize',
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'flex-end',
    padding: 3,
    boxSizing: 'border-box',
  };

  // L-shaped tick marks using two lines
  const lineColor = hovered
    ? 'var(--color-text-secondary)'
    : 'var(--color-text-tertiary)';

  const svgStyle: CSSProperties = {
    display: 'block',
    transition: 'color var(--transition-fast)',
    color: lineColor,
  };

  return (
    <div
      style={containerStyle}
      onMouseDown={onMouseDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title="Drag to resize"
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        style={svgStyle}
      >
        {/* Three diagonal tick marks — bottom-right resize indicator */}
        <line x1="9" y1="3" x2="3" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="9" y1="6" x2="6" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="9" y1="9" x2="9" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  );
}

export default ResizeHandle;
