// ---------------------------------------------------------------------------
// Smart Money — Notable-Filer Tracking
// Follow notable 13F managers, corporate insiders, and politicians using
// real 13F-HR / Form 4 / STOCK Act filings already ingested by the platform.
// Real backend: src/api/routers/smart_money.py (/v1/smart-money/*).
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useNotableInvestors,
  useCongressionalTrades,
  useSmartMoneyConsensus,
} from '@/api/hooks/useSmartMoney';

// --- Real API response shapes (src/schemas/smart_money.py) ------------------

interface NotableInvestorApi {
  key: string;
  display_name: string;
  category: string; // GURU_13F / INSIDER_FORM4 / POLITICIAN
  vehicle: string | null;
  role: string | null;
  chamber: string | null;
  party: string | null;
  state: string | null;
  tags: string[];
  notes: string | null;
}

interface CongressionalTradeApi {
  id: string;
  politician_name: string;
  chamber: string | null;
  party: string | null;
  state: string | null;
  ticker: string | null;
  asset_description: string | null;
  transaction_type: string;
  transaction_date: string;
  disclosure_date: string | null;
  midpoint_amount: number | null;
  size_bucket: string | null;
  disclosure_lag_days: number | null;
  is_late_disclosure: boolean | null;
  committee_conflict: boolean | null;
  conflict_committee: string | null;
}

interface ConsensusRowApi {
  ticker: string;
  buyers: string[];
  sellers: string[];
  net_score: number;
  participants: number;
  signal: string;
}

const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'GURU_13F', label: '13F Managers' },
  { value: 'INSIDER_FORM4', label: 'Insiders' },
  { value: 'POLITICIAN', label: 'Politicians' },
];

function LoadingBlock({ height = '80px' }: { height?: string }) {
  return (
    <div
      style={{
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-md)',
      }}
    />
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <div className="terminal-panel" style={{ borderLeft: '3px solid var(--color-signal-negative)' }}>
      <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>{message}</span>
    </div>
  );
}

function EmptyNote({ message }: { message: string }) {
  return (
    <div style={{ padding: '24px 16px', textAlign: 'center' }}>
      <span className="terminal-label">{message}</span>
    </div>
  );
}

function signalBadgeClass(signal: string): string {
  const s = signal.toUpperCase();
  if (s.includes('BULLISH') || s.includes('BUY') || s.includes('ACCUMULAT')) return 'terminal-badge terminal-badge-positive';
  if (s.includes('BEARISH') || s.includes('SELL') || s.includes('EXIT')) return 'terminal-badge terminal-badge-negative';
  return 'terminal-badge terminal-badge-neutral';
}

export default function SmartMoneyPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState('');
  const [politicianFilter, setPoliticianFilter] = useState('');
  const [tickerFilter, setTickerFilter] = useState('');

  const { data: investorsRaw, isLoading: loadingInvestors, isError: errorInvestors } = useNotableInvestors(
    category || undefined,
  ) as { data: NotableInvestorApi[] | undefined; isLoading: boolean; isError: boolean };

  const { data: tradesRaw, isLoading: loadingTrades, isError: errorTrades } = useCongressionalTrades({
    politician: politicianFilter || undefined,
    ticker: tickerFilter || undefined,
  }) as { data: CongressionalTradeApi[] | undefined; isLoading: boolean; isError: boolean };

  const { data: consensusRaw, isLoading: loadingConsensus, isError: errorConsensus } = useSmartMoneyConsensus() as {
    data: ConsensusRowApi[] | undefined;
    isLoading: boolean;
    isError: boolean;
  };

  const investors = Array.isArray(investorsRaw) ? investorsRaw : [];
  const trades = Array.isArray(tradesRaw) ? tradesRaw : [];
  const consensus = Array.isArray(consensusRaw) ? consensusRaw : [];

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)' }}>Smart Money</h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          Notable 13F managers, corporate insiders, and politicians — tracked from real public filings
        </p>
      </div>

      {/* Notable Investors Registry */}
      <div className="terminal-panel" style={{ marginBottom: 'var(--panel-gap)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h2 className="terminal-section-title" style={{ margin: 0 }}>Notable Investors</h2>
          <div style={{ display: 'flex', gap: '6px' }}>
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                onClick={() => setCategory(c.value)}
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 'var(--text-xs)',
                  padding: '4px 10px',
                  borderRadius: '3px',
                  border: '1px solid var(--color-surface-border)',
                  background: category === c.value ? 'var(--color-accent-primary)' : 'transparent',
                  color: category === c.value ? '#fff' : 'var(--color-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {loadingInvestors ? (
          <LoadingBlock height="200px" />
        ) : errorInvestors ? (
          <ErrorNote message="Failed to load the notable-investor registry." />
        ) : investors.length === 0 ? (
          <EmptyNote message="No notable investors match this filter." />
        ) : (
          <table className="terminal-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Vehicle / Role</th>
                <th>Location</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {investors.map((inv) => {
                const clickable = inv.category === 'GURU_13F';
                return (
                  <tr
                    key={inv.key}
                    style={{ cursor: clickable ? 'pointer' : 'default' }}
                    onClick={() => clickable && navigate(`/smart-money/${inv.key}`)}
                  >
                    <td style={{ fontWeight: 600, color: clickable ? 'var(--color-accent-primary)' : 'var(--color-text-primary)' }}>
                      {inv.display_name}
                    </td>
                    <td><span className="terminal-badge terminal-badge-neutral">{inv.category.replace('_', ' ')}</span></td>
                    <td className="terminal-label">{inv.vehicle ?? inv.role ?? '—'}</td>
                    <td className="terminal-label">
                      {[inv.chamber, inv.state, inv.party].filter(Boolean).join(' · ') || '—'}
                    </td>
                    <td className="terminal-label">{inv.tags.length > 0 ? inv.tags.join(', ') : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Congressional Trades */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Congressional Trades (STOCK Act)</h2>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
            <input
              type="text"
              value={politicianFilter}
              onChange={(e) => setPoliticianFilter(e.target.value)}
              placeholder="Filter by politician"
              style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: '6px 8px', background: 'var(--color-surface-void)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)', flex: 1 }}
            />
            <input
              type="text"
              value={tickerFilter}
              onChange={(e) => setTickerFilter(e.target.value.toUpperCase())}
              placeholder="Ticker"
              style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', padding: '6px 8px', background: 'var(--color-surface-void)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', color: 'var(--color-text-primary)', width: '100px' }}
            />
          </div>
          {loadingTrades ? (
            <LoadingBlock height="220px" />
          ) : errorTrades ? (
            <ErrorNote message="Failed to load congressional trades." />
          ) : trades.length === 0 ? (
            <EmptyNote message="No congressional trades match this filter." />
          ) : (
            <div style={{ maxHeight: '360px', overflow: 'auto' }}>
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>Politician</th>
                    <th>Ticker</th>
                    <th>Type</th>
                    <th className="right">Amount</th>
                    <th>Date</th>
                    <th>Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t) => (
                    <tr key={t.id}>
                      <td>{t.politician_name}</td>
                      <td style={{ fontWeight: 600 }}>{t.ticker ?? '—'}</td>
                      <td>
                        <span className={t.transaction_type?.toUpperCase().includes('SALE') ? 'terminal-badge terminal-badge-negative' : 'terminal-badge terminal-badge-positive'}>
                          {t.transaction_type}
                        </span>
                      </td>
                      <td className="right">{t.midpoint_amount != null ? `$${t.midpoint_amount.toLocaleString()}` : '—'}</td>
                      <td className="terminal-label">{t.transaction_date}</td>
                      <td>
                        {t.is_late_disclosure && <span className="terminal-badge terminal-badge-warning" style={{ marginRight: '4px' }}>Late</span>}
                        {t.committee_conflict && <span className="terminal-badge terminal-badge-negative">Conflict</span>}
                        {!t.is_late_disclosure && !t.committee_conflict && '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Consensus */}
        <div className="terminal-panel">
          <h2 className="terminal-section-title">Smart-Money Consensus</h2>
          <p className="terminal-label" style={{ marginTop: '-8px', marginBottom: '10px' }}>
            Securities multiple tracked 13F managers are accumulating or exiting together
          </p>
          {loadingConsensus ? (
            <LoadingBlock height="220px" />
          ) : errorConsensus ? (
            <ErrorNote message="Failed to load smart-money consensus." />
          ) : consensus.length === 0 ? (
            <EmptyNote message="No consensus signals yet — needs 2+ tracked managers with overlapping positions." />
          ) : (
            <div style={{ maxHeight: '360px', overflow: 'auto' }}>
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th className="right">Net Score</th>
                    <th className="right">Participants</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {consensus.map((c) => (
                    <tr key={c.ticker}>
                      <td style={{ fontWeight: 600 }}>{c.ticker}</td>
                      <td className="right">{c.net_score >= 0 ? '+' : ''}{c.net_score}</td>
                      <td className="right">{c.participants}</td>
                      <td><span className={signalBadgeClass(c.signal)}>{c.signal}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
