import type { ReactNode, CSSProperties } from 'react';

export interface AnimatedPanelProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

export function AnimatedPanel({ children, delay = 0, className }: AnimatedPanelProps) {
  const style: CSSProperties = {
    animation: `fadeIn 200ms ease-out both`,
    animationDelay: delay > 0 ? `${delay}ms` : undefined,
  };

  return (
    <div style={style} className={className}>
      {children}
    </div>
  );
}

export default AnimatedPanel;
