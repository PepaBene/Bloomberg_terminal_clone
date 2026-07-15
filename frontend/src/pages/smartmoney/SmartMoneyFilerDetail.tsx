// ---------------------------------------------------------------------------
// Smart Money — Filer Detail
// Quarter-over-quarter 13F activity profile for a single notable manager
// (e.g. Michael Burry / Scion). Real backend: GET /v1/smart-money/filers/{key}/profile.
// ---------------------------------------------------------------------------
import { useParams, useNavigate } from 'react-router-dom';
import { useFilerProfile } from '@/api/hooks/useSmartMoney';

// --- Real API response shapes (src/schemas/smart_money.py) ------------------

interface HoldingItemApi {
  ticker: string | null;
  name: string | null;
  market_value: number | null;
  percent_of_portfolio: number | null;
  shares: number | null;
  conviction: number | null;
  is_new_position: boolean | null;
  shares_change_pct: number | null;
}

interface FilerProfileApi {
  display_name: string;
  category: string;
  num_holdings: number;
  total_value: number;
  top5_concentration_pct: number;
  turnover: number;
  new_positions: HoldingItemApi[];
  exited_positions: HoldingItemApi[];
  increased_positions: HoldingItemApi[];
  decreased_positions: HoldingItemApi[];
  top_holdings: HoldingItemApi[];
}

function formatMoney(v: number | null): string {
  if (v == null) return '—';
  if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function LoadingSkeleton() {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ height: '28px', width: '260px', background: 'var(--color-surface-raised)', borderRadius: '4px' }} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginTop: '16px' }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="terminal-panel" style={{ height: '64px' }} />
        ))}
      </div>
    </div>
  );
}

function HoldingsTable({ title, rows }: { title: string; rows: HoldingItemApi[] }) {
  return (
    <div className="terminal-panel">
      <h2 className="terminal-section-title">{title}</h2>
      {rows.length === 0 ? (
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <span className="terminal-label">None this quarter</span>
        </div>
      ) : (
        <table className="terminal-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th className="right">Mkt Value</th>
              <th className="right">% Portfolio</th>
              <th className="right">Chg %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h, i) => (
              <tr key={`${h.ticker ?? h.name ?? i}`}>
                <td style={{ fontWeight: 600, color: 'var(--color-accent-primary)' }}>{h.ticker ?? '—'}</td>
                <td className="terminal-label">{h.name ?? '—'}</td>
                <td className="right">{formatMoney(h.market_value)}</td>
                <td className="right">{h.percent_of_portfolio != null ? `${h.percent_of_portfolio.toFixed(1)}%` : '—'}</td>
                <td className="right" style={{ color: h.shares_change_pct != null ? (h.shares_change_pct >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)') : 'var(--color-text-primary)' }}>
                  {h.shares_change_pct != null ? `${h.shares_change_pct >= 0 ? '+' : ''}${h.shares_change_pct.toFixed(1)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function SmartMoneyFilerDetail() {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();

  const { data: profile, isLoading, isError, error } = useFilerProfile(key) as {
    data: FilerProfileApi | undefined;
    isLoading: boolean;
    isError: boolean;
    error: unknown;
  };

  if (isLoading) return <LoadingSkeleton />;

  if (isError) {
    const message = error instanceof Error && error.message ? error.message : 'Failed to load this filer’s profile.';
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => navigate('/smart-money')} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: '12px' }}>
          &larr; Back to Smart Money
        </button>
        <div className="terminal-panel" style={{ borderLeft: '3px solid var(--color-signal-negative)' }}>
          <span className="terminal-label" style={{ color: 'var(--color-signal-negative)' }}>{message}</span>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div style={{ padding: '16px' }}>
        <span className="terminal-label">No profile data available.</span>
      </div>
    );
  }

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <button onClick={() => navigate('/smart-money')} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: '12px' }}>
        &larr; Back to Smart Money
      </button>
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)' }}>{profile.display_name}</h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          {profile.category.replace('_', ' ')} — quarter-over-quarter 13F activity
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {[
          { label: 'Holdings', value: String(profile.num_holdings) },
          { label: 'Total Value', value: formatMoney(profile.total_value) },
          { label: 'Top 5 Concentration', value: `${profile.top5_concentration_pct.toFixed(1)}%` },
          { label: 'Turnover', value: `${(profile.turnover * 100).toFixed(1)}%` },
        ].map((kpi) => (
          <div key={kpi.label} className="terminal-panel" style={{ textAlign: 'center', padding: '10px' }}>
            <div className="terminal-label">{kpi.label}</div>
            <div className="terminal-hero" style={{ fontSize: 'var(--text-lg)', marginTop: '4px' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--panel-gap)' }}>
        <HoldingsTable title="Top Holdings" rows={profile.top_holdings} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)' }}>
          <HoldingsTable title="New Positions" rows={profile.new_positions} />
          <HoldingsTable title="Increased Positions" rows={profile.increased_positions} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)' }}>
          <HoldingsTable title="Exited Positions" rows={profile.exited_positions} />
          <HoldingsTable title="Decreased Positions" rows={profile.decreased_positions} />
        </div>
      </div>
    </div>
  );
}
