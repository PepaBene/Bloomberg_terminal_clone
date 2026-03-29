import { useState, useMemo, useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SanctionRecord {
  country: string;
  programs: number;
  targets: number;
  trajectory: string;
  lastUpdated: string;
}

export interface SanctionsTableProps {
  sanctions: SanctionRecord[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

type SortKey = keyof SanctionRecord;
type SortDir = 'asc' | 'desc';

const TRAJECTORY_COLORS: Record<string, string> = {
  ESCALATING: 'var(--color-signal-negative)',
  STABLE: 'var(--color-signal-neutral)',
  DE_ESCALATING: 'var(--color-signal-positive)',
};

function trajectoryColor(t: string): string {
  return TRAJECTORY_COLORS[t.toUpperCase()] ?? 'var(--color-signal-neutral)';
}

function trajectoryLabel(t: string): string {
  return t.replace(/_/g, '-');
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function SanctionsTable({
  sanctions,
  className,
}: SanctionsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('country');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('asc');
      }
    },
    [sortKey],
  );

  const sorted = useMemo(() => {
    const copy = [...sanctions];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDir === 'asc' ? av - bv : bv - av;
      }
      const sa = String(av);
      const sb = String(bv);
      return sortDir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
    return copy;
  }, [sanctions, sortKey, sortDir]);

  const columns: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
    { key: 'country', label: 'Country', align: 'left' },
    { key: 'programs', label: 'Programs', align: 'right' },
    { key: 'targets', label: 'Targets', align: 'right' },
    { key: 'trajectory', label: 'Trajectory', align: 'left' },
    { key: 'lastUpdated', label: 'Last Updated', align: 'left' },
  ];

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return null;
    return (
      <span
        style={{
          fontSize: '8px',
          marginLeft: '3px',
          color: 'var(--color-accent-primary)',
        }}
      >
        {sortDir === 'asc' ? '\u25B2' : '\u25BC'}
      </span>
    );
  };

  return (
    <div className={clsx('overflow-auto', className)}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-sm)',
        }}
      >
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                style={{
                  textAlign: col.align,
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  color: 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  padding: '6px 8px',
                  borderBottom: '1px solid var(--color-surface-border)',
                  whiteSpace: 'nowrap',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                {col.label}
                {sortIndicator(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => {
            const tColor = trajectoryColor(s.trajectory);
            return (
              <tr
                key={s.country}
                style={{
                  borderBottom: '1px solid var(--color-surface-border)',
                }}
              >
                <td
                  style={{
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {s.country}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {s.programs.toLocaleString()}
                </td>

                <td
                  style={{
                    textAlign: 'right',
                    padding: '6px 8px',
                    color: 'var(--color-text-primary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {s.targets.toLocaleString()}
                </td>

                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 500,
                      color: tColor,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '2px 8px',
                      border: `1px solid ${tColor}`,
                      borderRadius: '9999px',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {trajectoryLabel(s.trajectory)}
                  </span>
                </td>

                <td
                  style={{
                    padding: '6px 8px',
                    color: 'var(--color-text-tertiary)',
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {s.lastUpdated}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
