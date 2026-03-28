import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface Holder {
  name: string;
  shares: number;
  pctOwned: number;
  change: number;
  value: number;
}

export interface OwnershipSummaryProps {
  holders: Holder[];
  insiderPct: number;
  institutionalPct: number;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtNum(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toLocaleString();
}

function fmtPct(n: number): string {
  return `${n.toFixed(2)}%`;
}

function fmtChange(n: number): string {
  const sign = n > 0 ? '+' : '';
  return `${sign}${fmtNum(n)}`;
}

/* ------------------------------------------------------------------ */
/*  Ownership Bar                                                      */
/* ------------------------------------------------------------------ */

function OwnershipBar({
  insiderPct,
  institutionalPct,
}: {
  insiderPct: number;
  institutionalPct: number;
}) {
  const retailPct = Math.max(0, 100 - insiderPct - institutionalPct);

  return (
    <div className="flex flex-col gap-1.5">
      {/* Bar */}
      <div
        className="flex overflow-hidden"
        style={{
          height: 8,
          borderRadius: 'var(--radius-sm)',
          background: 'var(--color-surface-overlay)',
        }}
      >
        <div
          style={{
            width: `${insiderPct}%`,
            background: 'var(--color-signal-highlight)',
            transition: 'width var(--transition-normal)',
          }}
        />
        <div
          style={{
            width: `${institutionalPct}%`,
            background: 'var(--color-accent-primary)',
            transition: 'width var(--transition-normal)',
          }}
        />
        <div
          style={{
            width: `${retailPct}%`,
            background: 'var(--color-text-tertiary)',
            transition: 'width var(--transition-normal)',
          }}
        />
      </div>

      {/* Legend */}
      <div
        className="flex gap-4"
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <span className="flex items-center gap-1">
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: 2,
              background: 'var(--color-signal-highlight)',
            }}
          />
          Insider {insiderPct.toFixed(1)}%
        </span>
        <span className="flex items-center gap-1">
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: 2,
              background: 'var(--color-accent-primary)',
            }}
          />
          Institutional {institutionalPct.toFixed(1)}%
        </span>
        <span className="flex items-center gap-1">
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: 2,
              background: 'var(--color-text-tertiary)',
            }}
          />
          Retail {retailPct.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function OwnershipSummary({
  holders,
  insiderPct,
  institutionalPct,
  className,
}: OwnershipSummaryProps) {
  return (
    <div className={clsx('terminal-panel flex flex-col gap-3', className)}>
      <h3 className="terminal-section-title">Ownership Summary</h3>

      <OwnershipBar insiderPct={insiderPct} institutionalPct={institutionalPct} />

      {/* Top holders table */}
      <div className="overflow-auto">
        <table className="terminal-table">
          <thead>
            <tr>
              <th>Holder</th>
              <th className="right">Shares</th>
              <th className="right">% Owned</th>
              <th className="right">Change</th>
              <th className="right">Value</th>
            </tr>
          </thead>
          <tbody>
            {holders.map((h) => {
              const changeColor =
                h.change > 0
                  ? 'var(--color-signal-positive)'
                  : h.change < 0
                    ? 'var(--color-signal-negative)'
                    : 'var(--color-text-primary)';

              return (
                <tr key={h.name}>
                  <td>{h.name}</td>
                  <td className="right">{fmtNum(h.shares)}</td>
                  <td className="right">{fmtPct(h.pctOwned)}</td>
                  <td className="right" style={{ color: changeColor }}>
                    {fmtChange(h.change)}
                  </td>
                  <td className="right">${fmtNum(h.value)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
