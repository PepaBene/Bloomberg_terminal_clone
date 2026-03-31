import type { CSSProperties } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import type { Column } from '@/components/ui/DataTable';
import { QualityScoreCell } from '@/components/ui/QualityScoreCell';

export interface HoldingRow extends Record<string, unknown> {
  ticker: string;
  name: string;
  weight: number;
  shares: number;
  price: number;
  costBasis: number;
  pnl: number;
  pnlPct: number;
  sector: string;
  qualityTier?: 1 | 2 | 3 | 4 | 5;
}

export interface HoldingsTableProps {
  holdings: HoldingRow[];
  onRowClick?: (h: HoldingRow) => void;
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function WeightBar({ weight, maxWeight }: { weight: number; maxWeight: number }) {
  const pct = maxWeight > 0 ? (weight / maxWeight) * 100 : 0;
  const barStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    width: '100%',
  };
  const trackStyle: CSSProperties = {
    flex: 1,
    height: '4px',
    background: 'var(--color-surface-overlay)',
    borderRadius: '2px',
    overflow: 'hidden',
  };
  const fillStyle: CSSProperties = {
    height: '100%',
    width: `${pct}%`,
    background: 'var(--color-accent-primary)',
    borderRadius: '2px',
  };
  return (
    <div style={barStyle}>
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-xs)',
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--color-text-primary)',
          minWidth: '36px',
          textAlign: 'right',
        }}
      >
        {weight.toFixed(1)}%
      </span>
      <div style={trackStyle}>
        <div style={fillStyle} />
      </div>
    </div>
  );
}

export function HoldingsTable({ holdings, onRowClick }: HoldingsTableProps) {
  const maxWeight = Math.max(...holdings.map((h) => h.weight), 1);

  const columns: Column<HoldingRow>[] = [
    {
      key: 'ticker',
      name: 'Ticker',
      width: '80px',
      format: (value) => (
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontWeight: 700,
            color: 'var(--color-accent-primary)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: 'name',
      name: 'Name',
      width: '180px',
      format: (value) => (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: 'weight',
      name: 'Weight',
      width: '120px',
      format: (value, _row) => (
        <WeightBar weight={value as number} maxWeight={maxWeight} />
      ),
    },
    {
      key: 'shares',
      name: 'Shares',
      align: 'right',
      width: '80px',
      format: (value) => (
        <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
          {(value as number).toLocaleString()}
        </span>
      ),
    },
    {
      key: 'price',
      name: 'Price',
      align: 'right',
      width: '90px',
      format: (value) => (
        <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
          ${(value as number).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'costBasis',
      name: 'Cost Basis',
      align: 'right',
      width: '90px',
      format: (value) => (
        <span style={{ fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums' }}>
          ${(value as number).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'pnl',
      name: 'P&L $',
      align: 'right',
      width: '100px',
      format: (value) => {
        const v = value as number;
        const sign = v >= 0 ? '+' : '';
        return (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              color: signalColor(v),
            }}
          >
            {sign}${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        );
      },
    },
    {
      key: 'pnlPct',
      name: 'P&L %',
      align: 'right',
      width: '80px',
      format: (value) => {
        const v = value as number;
        const sign = v >= 0 ? '+' : '';
        return (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontVariantNumeric: 'tabular-nums',
              color: signalColor(v),
            }}
          >
            {sign}{v.toFixed(2)}%
          </span>
        );
      },
    },
    {
      key: 'sector',
      name: 'Sector',
      width: '120px',
      format: (value) => (
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
          {value as string}
        </span>
      ),
    },
    {
      key: 'qualityTier',
      name: 'Quality',
      width: '80px',
      align: 'center',
      format: (value) => {
        if (value == null) return null;
        // Map 1-5 tier to a 0-100 score for QualityScoreCell
        const score = (value as number) * 20;
        return <QualityScoreCell score={score} max={100} />;
      },
    },
  ];

  return (
    <div className="animate-in">
      <DataTable<HoldingRow>
        columns={columns}
        data={holdings}
        onRowClick={onRowClick ? (row) => onRowClick(row) : undefined}
        sortable
        compact
      />
    </div>
  );
}

export default HoldingsTable;
