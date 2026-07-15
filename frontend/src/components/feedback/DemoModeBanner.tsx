import type { ReactNode } from 'react';

export interface DemoModeBannerProps {
  /**
   * Disclosure text. Defaults to the generic "showing sample data" message.
   * Pass a more specific reason where one is known (e.g. which endpoint is
   * unavailable).
   */
  message?: ReactNode;
  /**
   * Visual weight. `warning` (amber) for genuine mock/fallback substitution;
   * `info` (muted) for "not yet available" placeholders that aren't errors.
   */
  severity?: 'warning' | 'info';
  /** Extra style overrides for layout (margins, etc). */
  style?: React.CSSProperties;
}

/**
 * A small, honest "you are not looking at live data" strip.
 *
 * Generalized from the one-off banner ScreenerDashboard used to disclose its
 * demo-mode fallback — the only page in the app that told the user when it had
 * substituted mock data. Use it anywhere a page renders sample/placeholder data
 * instead of a real backend response, so the fallback is never silent.
 */
export function DemoModeBanner({
  message = 'Demo mode — showing sample data. Live data is unavailable.',
  severity = 'warning',
  style,
}: DemoModeBannerProps) {
  const color =
    severity === 'warning'
      ? 'var(--color-signal-warning)'
      : 'var(--color-text-secondary)';
  return (
    <div
      role="status"
      style={{
        padding: '8px 12px',
        marginBottom: '8px',
        borderRadius: '4px',
        background: `color-mix(in srgb, ${color} 10%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-xs)',
        color,
        ...style,
      }}
    >
      {message}
    </div>
  );
}
