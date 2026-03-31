import type { CSSProperties } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import type { Column } from '@/components/ui/DataTable';

export interface AttributionSector {
  name: string;
  portfolioWeight: number;
  benchmarkWeight: number;
  portfolioReturn: number;
  benchmarkReturn: number;
  allocation: number;
  selection: number;
  total: number;
  [key: string]: unknown;
}

export interface AttributionTableProps {
  sectors: AttributionSector[];
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function pctCell(value: unknown, colorize = false) {
  const v = value as number;
  const sign = v >= 0 ? '+' : '';
  return (
    <span
      style={{
        fontFamily: 'var(--font-data)',
        fontVariantNumeric: 'tabular-nums',
        color: colorize ? signalColor(v) : 'var(--color-text-primary)',
      }}
    >
      {sign}{v.toFixed(2)}%
    </span>
  );
}

const columns: Column<AttributionSector>[] = [
  {
    key: 'name',
    name: 'Sector',
    width: '140px',
    format: (value) => (
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>
        {value as string}
      </span>
    ),
  },
  {
    key: 'portfolioWeight',
    name: 'Port W%',
    align: 'right',
    width: '80px',
    format: (v) => pctCell(v),
  },
  {
    key: 'benchmarkWeight',
    name: 'Bench W%',
    align: 'right',
    width: '80px',
    format: (v) => pctCell(v),
  },
  {
    key: 'portfolioReturn',
    name: 'Port R%',
    align: 'right',
    width: '80px',
    format: (v) => pctCell(v, true),
  },
  {
    key: 'benchmarkReturn',
    name: 'Bench R%',
    align: 'right',
    width: '80px',
    format: (v) => pctCell(v, true),
  },
  {
    key: 'allocation',
    name: 'Allocation',
    align: 'right',
    width: '90px',
    format: (v) => pctCell(v, true),
  },
  {
    key: 'selection',
    name: 'Selection',
    align: 'right',
    width: '90px',
    format: (v) => pctCell(v, true),
  },
  {
    key: 'total',
    name: 'Total',
    align: 'right',
    width: '80px',
    format: (v) => pctCell(v, true),
  },
];

function sumField(sectors: AttributionSector[], field: keyof AttributionSector): number {
  return sectors.reduce((acc, s) => acc + (s[field] as number), 0);
}

export function AttributionTable({ sectors }: AttributionTableProps) {
  const footerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 'var(--space-4)',
    paddingTop: 'var(--space-2)',
    borderTop: '1px solid var(--color-surface-border)',
    marginTop: 'var(--space-1)',
  };

  const footerItemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '2px',
  };

  const totalAllocation = sumField(sectors, 'allocation');
  const totalSelection = sumField(sectors, 'selection');
  const totalTotal = sumField(sectors, 'total');

  return (
    <div className="animate-in">
      <DataTable<AttributionSector>
        columns={columns}
        data={sectors}
        sortable
        compact
      />
      <div style={footerStyle}>
        {[
          { label: 'Allocation', value: totalAllocation },
          { label: 'Selection', value: totalSelection },
          { label: 'Total', value: totalTotal },
        ].map(({ label, value }) => {
          const sign = value >= 0 ? '+' : '';
          return (
            <div key={label} style={footerItemStyle}>
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {label}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 700,
                  color: signalColor(value),
                }}
              >
                {sign}{value.toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AttributionTable;
