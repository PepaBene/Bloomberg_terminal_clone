import { useToastStore, type ToastVariant } from '@/stores/toastStore';

const VARIANT_COLOR: Record<ToastVariant, string> = {
  error: 'var(--color-signal-negative)',
  success: 'var(--color-signal-positive)',
  warning: 'var(--color-signal-warning)',
  info: 'var(--color-accent-primary)',
};

/**
 * Global toast/inline-error stack. Mounted once (see App.tsx) and driven by
 * `useToastStore` -- call `useToastStore.getState().showToast(message)` from
 * anywhere (mutation `onError`, a `catch` block, etc.) to surface an error
 * to the user instead of a silent `console.warn`/`console.error` (P4-F-023,
 * P4-F-021).
 */
export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismissToast = useToastStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '16px',
        right: '16px',
        zIndex: 2000,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        maxWidth: '360px',
      }}
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          onClick={() => dismissToast(toast.id)}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-primary)',
            background: 'var(--color-surface-raised)',
            border: `1px solid ${VARIANT_COLOR[toast.variant]}`,
            borderLeft: `3px solid ${VARIANT_COLOR[toast.variant]}`,
            borderRadius: '4px',
            padding: '10px 14px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            cursor: 'pointer',
          }}
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
