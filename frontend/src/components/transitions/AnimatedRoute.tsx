import { useRef, useEffect, type ReactNode, type CSSProperties } from 'react';

export interface AnimatedRouteProps {
  children: ReactNode;
  route: string;
}

export function AnimatedRoute({ children, route }: AnimatedRouteProps) {
  const ref = useRef<HTMLDivElement>(null);
  const prevRoute = useRef<string>(route);

  useEffect(() => {
    if (!ref.current) return;
    if (prevRoute.current === route) return;

    // Trigger slide-in animation on route change
    ref.current.style.animation = 'none';
    // Force reflow
    void ref.current.offsetHeight;
    ref.current.style.animation = 'slideInLeft 200ms ease-out both';
    prevRoute.current = route;
  }, [route]);

  const style: CSSProperties = {
    width: '100%',
    height: '100%',
    animation: 'fadeIn 200ms ease-out both',
  };

  return (
    <div ref={ref} style={style}>
      {children}
    </div>
  );
}

export default AnimatedRoute;
