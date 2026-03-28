export interface ErrorPanelProps {
  /** Error title (default "Error") */
  title?: string;
  /** Error message to display */
  message: string;
  /** Optional retry handler — renders a retry button when provided */
  onRetry?: () => void;
}

/**
 * Error state display for panels.
 * Red signal icon, message, and optional retry button.
 */
export function ErrorPanel({
  title = 'Error',
  message,
  onRetry,
}: ErrorPanelProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-3)',
        padding: 'var(--space-8) var(--space-4)',
        textAlign: 'center',
        minHeight: '120px',
      }}
    >
      {/* Warning icon */}
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        style={{ flexShrink: 0 }}
      >
        <path
          d="M12 2L1 21h22L12 2z"
          stroke="var(--color-signal-negative)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <line
          x1="12"
          y1="9"
          x2="12"
          y2="14"
          stroke="var(--color-signal-negative)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="12" cy="17" r="0.8" fill="var(--color-signal-negative)" />
      </svg>

      {/* Title */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-md)',
          fontWeight: 600,
          color: 'var(--color-signal-negative)',
        }}
      >
        {title}
      </span>

      {/* Message */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-secondary)',
          maxWidth: '320px',
          lineHeight: 1.5,
        }}
      >
        {message}
      </span>

      {/* Retry button */}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            marginTop: 'var(--space-1)',
            padding: 'var(--space-1) var(--space-4)',
            background: 'transparent',
            border: '1px solid var(--color-signal-negative)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-signal-negative)',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background var(--transition-fast)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              'rgba(224,82,82,0.12)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              'transparent';
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
