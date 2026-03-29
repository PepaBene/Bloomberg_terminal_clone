import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface GeopoliticalEvent {
  title: string;
  description: string;
  severity: string;
  countries: string[];
  startDate: string;
  status: string;
  commodityImpact?: string[];
  sectorImpact?: string[];
}

export interface GeopoliticalEventCardProps {
  event: GeopoliticalEvent;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'var(--color-signal-negative)',
  HIGH: 'var(--color-signal-warning)',
  MEDIUM: 'var(--color-accent-primary)',
  LOW: 'var(--color-signal-neutral)',
};

function severityColor(s: string): string {
  return SEVERITY_COLORS[s.toUpperCase()] ?? 'var(--color-signal-neutral)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function GeopoliticalEventCard({
  event,
  className,
}: GeopoliticalEventCardProps) {
  const sevColor = severityColor(event.severity);

  return (
    <div
      className={clsx('flex flex-col gap-3', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderLeft: `3px solid ${sevColor}`,
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '12px 16px',
      }}
    >
      {/* Header: title + severity */}
      <div className="flex items-start justify-between gap-3">
        <h4
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-md)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            margin: 0,
            lineHeight: '1.3',
          }}
        >
          {event.title}
        </h4>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: sevColor,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '2px 8px',
            border: `1px solid ${sevColor}`,
            borderRadius: '9999px',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {event.severity}
        </span>
      </div>

      {/* Description */}
      <p
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-secondary)',
          margin: 0,
          lineHeight: '1.5',
        }}
      >
        {event.description}
      </p>

      {/* Meta row: date, status */}
      <div
        className="flex items-center gap-3"
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
        }}
      >
        <span>{event.startDate}</span>
        <span
          style={{
            color: 'var(--color-signal-neutral)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {event.status}
        </span>
      </div>

      {/* Country chips */}
      {event.countries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {event.countries.map((c) => (
            <span
              key={c}
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                fontWeight: 500,
                color: 'var(--color-text-primary)',
                padding: '2px 8px',
                background: 'var(--color-surface-overlay, rgba(255,255,255,0.06))',
                borderRadius: '4px',
                whiteSpace: 'nowrap',
              }}
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Impact tags */}
      {((event.commodityImpact && event.commodityImpact.length > 0) ||
        (event.sectorImpact && event.sectorImpact.length > 0)) && (
        <div className="flex flex-wrap gap-1">
          {event.commodityImpact?.map((ci) => (
            <span
              key={ci}
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-signal-warning)',
                padding: '2px 8px',
                border: '1px solid var(--color-signal-warning)',
                borderRadius: '9999px',
                whiteSpace: 'nowrap',
              }}
            >
              {ci}
            </span>
          ))}
          {event.sectorImpact?.map((si) => (
            <span
              key={si}
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-accent-primary)',
                padding: '2px 8px',
                border: '1px solid var(--color-accent-primary)',
                borderRadius: '9999px',
                whiteSpace: 'nowrap',
              }}
            >
              {si}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
