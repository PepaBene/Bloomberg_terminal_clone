import { useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { api } from '@/api/client';

export interface TransactionFormProps {
  portfolioId: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

type Direction = 'BUY' | 'SELL';

export function TransactionForm({ portfolioId, onSuccess, onCancel }: TransactionFormProps) {
  const [ticker, setTicker] = useState('');
  const [direction, setDirection] = useState<Direction>('BUY');
  const [shares, setShares] = useState('');
  const [price, setPrice] = useState('');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rootStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    flexWrap: 'wrap',
    padding: 'var(--space-3) var(--panel-padding)',
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
  };

  const inputStyle: CSSProperties = {
    fontFamily: 'var(--font-data)',
    fontSize: 'var(--text-sm)',
    fontVariantNumeric: 'tabular-nums',
    color: 'var(--color-text-primary)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    padding: '4px 8px',
    height: '28px',
    outline: 'none',
  };

  const labelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    color: 'var(--color-text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginRight: '4px',
  };

  const toggleBtnStyle = (active: boolean, isPositive: boolean): CSSProperties => ({
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    padding: '4px 12px',
    height: '28px',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    cursor: 'pointer',
    color: active
      ? isPositive
        ? 'var(--color-signal-positive)'
        : 'var(--color-signal-negative)'
      : 'var(--color-text-tertiary)',
    background: active ? 'var(--color-surface-raised)' : 'transparent',
    transition: 'all 0.15s',
  });

  const submitStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    fontWeight: 600,
    padding: '4px 16px',
    height: '28px',
    background: 'var(--color-accent-primary)',
    color: 'var(--color-surface-void)',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.6 : 1,
    transition: 'opacity 0.15s',
  };

  const cancelStyle: CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-sm)',
    padding: '4px 12px',
    height: '28px',
    background: 'transparent',
    color: 'var(--color-text-tertiary)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
    cursor: 'pointer',
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ticker || !shares || !price) return;
    setLoading(true);
    setError(null);
    try {
      await api.post(`/v1/portfolios/${portfolioId}/transactions`, {
        ticker: ticker.toUpperCase().trim(),
        direction,
        shares: parseFloat(shares),
        price: parseFloat(price),
        date,
        notes: notes || undefined,
      });
      setTicker('');
      setShares('');
      setPrice('');
      setNotes('');
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="animate-in" style={rootStyle} onSubmit={handleSubmit}>
      <span style={labelStyle}>Ticker</span>
      <input
        style={{ ...inputStyle, width: '80px', textTransform: 'uppercase' }}
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="AAPL"
        maxLength={10}
        required
      />

      <span style={labelStyle}>Dir</span>
      <div style={{ display: 'flex', gap: '4px' }}>
        <button
          type="button"
          style={toggleBtnStyle(direction === 'BUY', true)}
          onClick={() => setDirection('BUY')}
        >
          BUY
        </button>
        <button
          type="button"
          style={toggleBtnStyle(direction === 'SELL', false)}
          onClick={() => setDirection('SELL')}
        >
          SELL
        </button>
      </div>

      <span style={labelStyle}>Shares</span>
      <input
        style={{ ...inputStyle, width: '90px' }}
        type="number"
        value={shares}
        onChange={(e) => setShares(e.target.value)}
        placeholder="100"
        min="0.0001"
        step="any"
        required
      />

      <span style={labelStyle}>Price</span>
      <input
        style={{ ...inputStyle, width: '90px' }}
        type="number"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        placeholder="150.00"
        min="0"
        step="any"
        required
      />

      <span style={labelStyle}>Date</span>
      <input
        style={{ ...inputStyle, width: '120px' }}
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        required
      />

      <span style={labelStyle}>Notes</span>
      <input
        style={{ ...inputStyle, width: '160px' }}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Optional note"
      />

      {error && (
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-signal-negative)',
          }}
        >
          {error}
        </span>
      )}

      <button type="submit" style={submitStyle} disabled={loading}>
        {loading ? 'Saving...' : 'Add'}
      </button>

      {onCancel && (
        <button type="button" style={cancelStyle} onClick={onCancel}>
          Cancel
        </button>
      )}
    </form>
  );
}

export default TransactionForm;
