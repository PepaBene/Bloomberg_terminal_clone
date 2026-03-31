import { useState } from 'react';
import type { CSSProperties } from 'react';

interface AnnotationPinProps {
  count: number;
  color: string;
  onClick: () => void;
}

function AnnotationPin({ count, color, onClick }: AnnotationPinProps) {
  const [hovered, setHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const pinStyle: CSSProperties = {
    position: 'absolute',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 20,
    height: 20,
    borderRadius: '50%',
    background: color,
    border: '1px solid rgba(255,255,255,0.15)',
    cursor: 'pointer',
    boxShadow: hovered ? 'var(--shadow-float)' : '0 1px 4px rgba(0,0,0,0.4)',
    transform: hovered ? 'scale(1.15)' : 'scale(1)',
    transition: 'transform var(--transition-fast), box-shadow var(--transition-fast)',
    zIndex: 10,
  };

  const badgeStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontSize: 9,
    fontWeight: 700,
    color: '#fff',
    fontVariantNumeric: 'tabular-nums',
    lineHeight: 1,
    userSelect: 'none',
  };

  const tooltipStyle: CSSProperties = {
    position: 'absolute',
    bottom: 'calc(100% + 6px)',
    left: '50%',
    transform: 'translateX(-50%)',
    background: 'var(--color-surface-overlay)',
    border: '1px solid var(--color-surface-border-strong)',
    borderRadius: 'var(--radius-sm)',
    padding: '3px var(--space-2)',
    whiteSpace: 'nowrap',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-secondary)',
    pointerEvents: 'none',
    boxShadow: 'var(--shadow-float)',
    zIndex: 20,
    opacity: showTooltip ? 1 : 0,
    transition: 'opacity var(--transition-fast)',
  };

  return (
    <div
      style={pinStyle}
      onClick={onClick}
      onMouseEnter={() => { setHovered(true); setShowTooltip(true); }}
      onMouseLeave={() => { setHovered(false); setShowTooltip(false); }}
    >
      <span style={badgeStyle}>{count > 99 ? '99+' : count}</span>
      <div style={tooltipStyle}>
        {count} annotation{count !== 1 ? 's' : ''}
      </div>
    </div>
  );
}

export default AnnotationPin;
