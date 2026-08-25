// ---------------------------------------------------------------------------
// Politicians — Congressional STOCK Act Trade Disclosures
//
// GET /v1/smart-money/congress (src/api/routers/smart_money.py) has real
// CongressionalTrade data with conflict/lag flags, but nothing in the
// frontend called it -- the NavRail's Smart $ flyout "Politicians" sub-item
// fell back to the parent /smart-money page. Wired here as its own route.
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { EmptyState } from '@/components/feedback';
import { api } from '@/api/client';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
};
const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
};
const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
  padding: '6px 10px', borderRadius: '4px',
  border: '1px solid var(--color-surface-border)',
  background: 'var(--color-surface-raised)', color: 'var(--color-text-primary)',
  outline: 'none',
};

interface CongressionalTradeDTO {
  id: string;
  politician_name: string;
  chamber: string | null;
  party: string | null;
  ticker: string | null;
  transaction_type: string;
  transaction_date: string;
  disclosure_date: string | null;
  amount_range_low: number | null;
  amount_range_high: number | null;
  disclosure_lag_days: number | null;
  is_late_disclosure: boolean | null;
  committee_conflict: boolean | null;
}

function fmtAmount(low: number | null, high: number | null): string {
  if (low == null && high == null) return '—';
  const f = (v: number) => `$${(v / 1000).toFixed(0)}K`;
  if (low != null && high != null) return `${f(low)}–${f(high)}`;
  return f((low ?? high)!);
}

export default function PoliticiansPage() {
  const [ticker, setTicker] = useState('');
  const { data, isLoading } = useQuery<CongressionalTradeDTO[]>({
    queryKey: ['smart-money', 'congress', ticker],
    queryFn: () => api.get('/v1/smart-money/congress', ticker ? { ticker } : undefined),
    retry: 0,
  });
  const trades = Array.isArray(data) ? data : [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '16px' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
            Politicians
          </h1>
          <p style={{ ...labelStyle, marginTop: '4px' }}>Congressional STOCK Act trade disclosures</p>
        </div>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Filter by ticker…"
          style={inputStyle}
        />
      </div>

      <div style={panelStyle}>
        {isLoading ? (
          <EmptyState icon="⏳" title="Loading…" />
        ) : trades.length === 0 ? (
          <EmptyState icon="🏛️" title="No congressional trades found" description="No STOCK Act disclosures match this filter." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Politician', 'Party', 'Ticker', 'Type', 'Amount', 'Trade Date', 'Disclosed', 'Lag (days)', 'Flags'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{t.politician_name}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{t.party ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{t.ticker ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.transaction_type}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtAmount(t.amount_range_low, t.amount_range_high)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{t.transaction_date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{t.disclosure_date ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: t.is_late_disclosure ? 'var(--color-signal-negative)' : undefined }}>{t.disclosure_lag_days ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    {t.committee_conflict ? <span className="terminal-badge terminal-badge-negative">Conflict</span> : ''}
                    {t.is_late_disclosure ? <span className="terminal-badge">Late</span> : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
