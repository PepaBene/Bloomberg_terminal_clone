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

function covenantStatusColor(status: string): string {
  const s = status.toUpperCase();
  if (s === 'COMPLIANT' || s === 'MET') return 'var(--color-signal-positive)';
  if (s === 'WARNING' || s === 'WATCH') return 'var(--color-signal-warning)';
  if (s === 'BREACHED' || s === 'VIOLATED') return 'var(--color-signal-negative)';
  return 'var(--color-signal-neutral)';
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

const thStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-xs)',
  fontWeight: 500,
  color: 'var(--color-text-secondary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  padding: '6px 8px',
  borderBottom: '1px solid var(--color-surface-border)',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '6px 8px',
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-sm)',
  fontVariantNumeric: 'tabular-nums',
  color: 'var(--color-text-primary)',
  borderBottom: '1px solid var(--color-surface-border)',
};

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
    <div className={clsx('flex flex-col gap-4', className)}>
      {/* Key terms — 2-column grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0',
        }}
      >
        {termPairs.map((t) => (
          <div
            key={t.label}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '6px 8px',
              borderBottom: '1px solid var(--color-surface-border)',
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
              marginBottom: '6px',
            }}
          >
            Call Schedule
          </h4>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...thStyle, textAlign: 'left' }}>Date</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Price</th>
              </tr>
            </thead>
            <tbody>
              {bond.callSchedule.map((c) => (
                <tr key={`${c.date}-${c.price}`}>
                  <td style={{ ...tdStyle, textAlign: 'left', fontFamily: 'var(--font-ui)' }}>
                    {c.date}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
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
              marginBottom: '6px',
            }}
          >
            Covenants
          </h4>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...thStyle, textAlign: 'left' }}>Type</th>
                <th style={{ ...thStyle, textAlign: 'left' }}>Description</th>
                <th style={{ ...thStyle, textAlign: 'left' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {bond.covenants.map((cv, i) => {
                const sColor = covenantStatusColor(cv.status);
                return (
                  <tr key={`${cv.type}-${i}`}>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: 'left',
                        fontFamily: 'var(--font-ui)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {cv.type}
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: 'left',
                        fontFamily: 'var(--font-ui)',
                        color: 'var(--color-text-secondary)',
                      }}
                    >
                      {cv.description}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'left' }}>
                      <span
                        style={{
                          fontFamily: 'var(--font-data)',
                          fontSize: 'var(--text-xs)',
                          fontWeight: 500,
                          color: sColor,
                          textTransform: 'uppercase',
                          letterSpacing: '0.06em',
                          padding: '2px 8px',
                          border: `1px solid ${sColor}`,
                          borderRadius: '9999px',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {cv.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
