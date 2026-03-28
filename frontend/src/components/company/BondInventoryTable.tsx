import { useState, useMemo, useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface BondRecord {
  cusip: string;
  coupon: number;
  maturity: string;
  outstanding: number;
  rating: string;
  spread: number;
  price: number;
  ytm: number;
}

export interface BondInventoryTableProps {
  bonds: BondRecord[];
  onBondClick?: (cusip: string) => void;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

type SortDir = 'asc' | 'desc';
type SortKey = keyof BondRecord;

function ratingTier(rating: string): 'ig-high' | 'ig-low' | 'hy' | 'distressed' {
  const upper = rating.toUpperCase().replace(/[+\-]/g, '');
  if (['AAA', 'AA'].includes(upper)) return 'ig-high';
  if (['A', 'BBB'].includes(upper)) return 'ig-low';
  if (['BB', 'B'].includes(upper)) return 'hy';
  return 'distressed';
}

function ratingColor(rating: string): string {
  const tier = ratingTier(rating);
  if (tier === 'ig-high') return 'var(--color-signal-positive)';
  if (tier === 'ig-low') return 'var(--color-accent-primary)';
  if (tier === 'hy') return 'var(--color-signal-warning)';
  return 'var(--color-signal-negative)';
}

function fmtMoney(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPct(n: number): string {
  return `${n.toFixed(3)}%`;
}

function fmtBps(n: number): string {
  return `${n.toFixed(0)}bp`;
}

function fmtPrice(n: number): string {
  return n.toFixed(3);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BondInventoryTable({
  bonds,
  onBondClick,
  className,
}: BondInventoryTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('maturity');
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
    const copy = [...bonds];
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
  }, [bonds, sortKey, sortDir]);

  const columns: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
    { key: 'cusip', label: 'CUSIP', align: 'left' },
    { key: 'coupon', label: 'Coupon', align: 'right' },
    { key: 'maturity', label: 'Maturity', align: 'left' },
    { key: 'outstanding', label: 'Outstanding', align: 'right' },
    { key: 'rating', label: 'Rating', align: 'left' },
    { key: 'spread', label: 'OAS', align: 'right' },
    { key: 'price', label: 'Price', align: 'right' },
    { key: 'ytm', label: 'YTM', align: 'right' },
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
    <div className={clsx('terminal-panel overflow-auto', className)}>
      <h3 className="terminal-section-title">Bond Inventory</h3>

      <table className="terminal-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(col.align === 'right' && 'right', 'cursor-pointer select-none')}
                onClick={() => handleSort(col.key)}
              >
                {col.label}
                {sortIndicator(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((b) => (
            <tr
              key={b.cusip}
              className={clsx(onBondClick && 'cursor-pointer')}
              onClick={onBondClick ? () => onBondClick(b.cusip) : undefined}
            >
              <td
                style={{
                  fontFamily: 'var(--font-data)',
                  color: 'var(--color-accent-primary)',
                }}
              >
                {b.cusip}
              </td>
              <td className="right">{fmtPct(b.coupon)}</td>
              <td>{b.maturity}</td>
              <td className="right">{fmtMoney(b.outstanding)}</td>
              <td style={{ color: ratingColor(b.rating) }}>{b.rating}</td>
              <td className="right">{fmtBps(b.spread)}</td>
              <td className="right">{fmtPrice(b.price)}</td>
              <td className="right">{fmtPct(b.ytm)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
