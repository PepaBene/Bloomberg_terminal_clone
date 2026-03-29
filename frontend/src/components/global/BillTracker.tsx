import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface BillRecord {
  id: string;
  title: string;
  type: string;
  status: string;
  sponsors: number;
  passageProbability: number;
  affectedSectors: string[];
  lastAction: string;
}

export interface BillTrackerProps {
  bill: BillRecord;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function probabilityColor(p: number): string {
  if (p > 50) return 'var(--color-signal-positive)';
  if (p >= 20) return 'var(--color-signal-warning)';
  return 'var(--color-signal-negative)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BillTracker({ bill, className }: BillTrackerProps) {
  const probColor = probabilityColor(bill.passageProbability);

  return (
    <div
      className={clsx('flex flex-col gap-3', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        padding: '12px 16px',
      }}
    >
      {/* Header: ID + type + status badge */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-accent-primary)',
              marginRight: '8px',
            }}
          >
            {bill.id}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              textTransform: 'uppercase',
            }}
          >
            {bill.type}
          </span>
        </div>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            color: 'var(--color-signal-neutral)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '2px 8px',
            border: '1px solid var(--color-signal-neutral)',
            borderRadius: '9999px',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {bill.status}
        </span>
      </div>

      {/* Title */}
      <h4
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          margin: 0,
          lineHeight: '1.4',
        }}
      >
        {bill.title}
      </h4>

      {/* Passage probability bar */}
      <div>
        <div
          className="flex items-center justify-between"
          style={{ marginBottom: '4px' }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Passage Probability
          </span>
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: probColor,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {bill.passageProbability}%
          </span>
        </div>
        <div
          style={{
            height: '6px',
            background: 'var(--color-surface-border)',
            borderRadius: '3px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${Math.max(0, Math.min(100, bill.passageProbability))}%`,
              height: '100%',
              background: probColor,
              borderRadius: '3px',
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      </div>

      {/* Meta: sponsors + last action */}
      <div
        className="flex items-center gap-3"
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-tertiary)',
        }}
      >
        <span>{bill.sponsors} sponsors</span>
        <span>{bill.lastAction}</span>
      </div>

      {/* Sector impact chips */}
      {bill.affectedSectors.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {bill.affectedSectors.map((s) => (
            <span
              key={s}
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
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
