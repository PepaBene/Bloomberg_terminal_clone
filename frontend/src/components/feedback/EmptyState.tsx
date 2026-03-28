import type { ReactNode } from 'react';

export interface EmptyStateProps {
  /** Large icon character or emoji (e.g. "📊") */
  icon?: ReactNode;
  /** Primary title */
  title: string;
  /** Optional description */
  description?: string;
  /** Optional CTA action */
  action?: { label: string; onClick: () => void };
}

/**
 * Empty state placeholder for panels with no data.
 * Centered layout with icon, title, description, and optional action button.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-2)',
        padding: 'var(--space-8) var(--space-4)',
        textAlign: 'center',
        minHeight: '120px',
      }}
    >
      {/* Icon */}
      {icon && (
        <span
          style={{
            fontSize: '28px',
            lineHeight: 1,
            color: 'var(--color-text-tertiary)',
            marginBottom: 'var(--space-1)',
            opacity: 0.6,
          }}
        >
          {icon}
        </span>
      )}

      {/* Title */}
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-md)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
        }}
      >
        {title}
      </span>

      {/* Description */}
      {description && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
            maxWidth: '320px',
            lineHeight: 1.5,
          }}
        >
          {description}
        </span>
      )}

      {/* Action button */}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          style={{
            marginTop: 'var(--space-2)',
            padding: 'var(--space-1) var(--space-4)',
            background: 'var(--color-accent-primary)',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            color: '#fff',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'opacity var(--transition-fast)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.opacity = '0.85';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.opacity = '1';
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
