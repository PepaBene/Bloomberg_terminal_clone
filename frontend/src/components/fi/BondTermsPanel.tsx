import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CallScheduleEntry {
  date: string;
  price: number;
}

export interface CovenantEntry {
  type: string;
  description: string;
  status: string;
}

export interface BondTerms {
  cusip: string;
  isin: string;
  coupon: number;
  frequency: string;
  maturity: string;
  issuer: string;
  rating: string;
  callSchedule?: CallScheduleEntry[];
  covenants?: CovenantEntry[];
}

export interface BondTermsPanelProps {
  bond: BondTerms;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function covenantBadgeClass(status: string): string {
  const s = status.toUpperCase();
  if (s === 'COMPLIANT' || s === 'MET') return 'terminal-badge terminal-badge-positive';
  if (s === 'WARNING' || s === 'WATCH') return 'terminal-badge terminal-badge-warning';
  if (s === 'BREACHED' || s === 'VIOLATED') return 'terminal-badge terminal-badge-negative';
  return 'terminal-badge terminal-badge-neutral';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BondTermsPanel({ bond, className }: BondTermsPanelProps) {
  const termPairs: { label: string; value: string }[] = [
    { label: 'CUSIP', value: bond.cusip },
    { label: 'ISIN', value: bond.isin },
    { label: 'Issuer', value: bond.issuer },
    { label: 'Coupon', value: `${bond.coupon.toFixed(3)}%` },
    { label: 'Frequency', value: bond.frequency },
    { label: 'Maturity', value: bond.maturity },
    { label: 'Rating', value: bond.rating },
  ];

  return (
    <div className={clsx('animate-in', className)} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Key terms -- 2-column grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 0,
        }}
      >
        {termPairs.map((t) => (
          <div
            key={t.label}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: 'var(--space-1) var(--space-2)',
              borderBottom: '1px solid var(--color-surface-border)',
              borderRadius: 0,
              transition: 'background 120ms ease',
              cursor: 'default',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--color-surface-overlay)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
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
              {t.label}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-primary)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {t.value}
            </span>
          </div>
        ))}
      </div>

      {/* Call schedule table */}
      {bond.callSchedule && bond.callSchedule.length > 0 && (
        <div>
          <h4
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              margin: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            Call Schedule
          </h4>
          <table className="terminal-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Date</th>
                <th className="right">Price</th>
              </tr>
            </thead>
            <tbody>
              {bond.callSchedule.map((c) => (
                <tr key={`${c.date}-${c.price}`}>
                  <td
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-sm)',
                    }}
                  >
                    {c.date}
                  </td>
                  <td
                    className="right"
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {c.price.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Covenant summary */}
      {bond.covenants && bond.covenants.length > 0 && (
        <div>
          <h4
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              margin: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            Covenants
          </h4>
          <table className="terminal-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Type</th>
                <th style={{ textAlign: 'left' }}>Description</th>
                <th style={{ textAlign: 'left' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {bond.covenants.map((cv, i) => (
                <tr key={`${cv.type}-${i}`}>
                  <td
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-sm)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {cv.type}
                  </td>
                  <td
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    {cv.description}
                  </td>
                  <td>
                    <span className={covenantBadgeClass(cv.status)}>
                      {cv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
