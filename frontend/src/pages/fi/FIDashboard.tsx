// ---------------------------------------------------------------------------
// Fixed Income Dashboard
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

// --- Helpers -----------------------------------------------------------------

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function regimeColor(regime: string): string {
  switch (regime) {
    case 'Tight':   return 'var(--color-signal-positive)';
    case 'Normal':  return 'var(--color-signal-neutral)';
    case 'Wide':    return 'var(--color-signal-warning)';
    case 'Stress':  return 'var(--color-signal-negative)';
    default:        return 'var(--color-text-secondary)';
  }
}

// --- Skeleton ----------------------------------------------------------------

function Skeleton({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-sm)',
      }}
    />
  );
}

// --- Mock Data (fallback) ----------------------------------------------------

interface YieldTenor {
  tenor: string;
  rate: number;
  change1d: number;
  change1w: number;
}

const MOCK_YIELD_CURVE: YieldTenor[] = [
  { tenor: '1M',  rate: 5.38, change1d: 0.00,  change1w: -0.02 },
  { tenor: '3M',  rate: 5.36, change1d: -0.01, change1w: -0.03 },
  { tenor: '6M',  rate: 5.27, change1d: -0.01, change1w: -0.05 },
  { tenor: '1Y',  rate: 5.02, change1d: -0.02, change1w: -0.08 },
  { tenor: '2Y',  rate: 4.62, change1d: -0.03, change1w: -0.12 },
  { tenor: '3Y',  rate: 4.42, change1d: -0.02, change1w: -0.10 },
  { tenor: '5Y',  rate: 4.28, change1d: -0.02, change1w: -0.08 },
  { tenor: '7Y',  rate: 4.30, change1d: -0.01, change1w: -0.06 },
  { tenor: '10Y', rate: 4.28, change1d: -0.03, change1w: -0.07 },
  { tenor: '20Y', rate: 4.52, change1d: -0.02, change1w: -0.04 },
  { tenor: '30Y', rate: 4.42, change1d: -0.02, change1w: -0.05 },
];

interface CreditIndex {
  name: string;
  oas: number;
  change1d: number;
  regime: string;
}

const MOCK_CREDIT: CreditIndex[] = [
  { name: 'IG Corporate OAS',  oas: 92,  change1d: -2, regime: 'Tight' },
  { name: 'HY Corporate OAS',  oas: 328, change1d: 4,  regime: 'Normal' },
  { name: 'IG Financial OAS',  oas: 78,  change1d: -1, regime: 'Tight' },
  { name: 'EM Sovereign OAS',  oas: 248, change1d: 3,  regime: 'Normal' },
];

interface RecentIssuance {
  issuer: string;
  coupon: string;
  maturity: string;
  size: string;
  rating: string;
  spread: string;
}

const MOCK_ISSUANCE: RecentIssuance[] = [
  { issuer: 'Apple Inc.',            coupon: '4.250%', maturity: '2034-03-15', size: '$3.0B', rating: 'AA+', spread: 'T+62' },
  { issuer: 'Goldman Sachs',         coupon: '5.125%', maturity: '2029-09-01', size: '$2.5B', rating: 'A-',  spread: 'T+108' },
  { issuer: 'Microsoft Corp.',       coupon: '4.000%', maturity: '2054-03-01', size: '$2.0B', rating: 'AAA', spread: 'T+55' },
  { issuer: 'Ford Motor Credit',     coupon: '5.750%', maturity: '2028-06-15', size: '$1.5B', rating: 'BBB-', spread: 'T+188' },
  { issuer: 'Amazon.com Inc.',       coupon: '4.125%', maturity: '2044-03-15', size: '$1.75B', rating: 'AA', spread: 'T+72' },
  { issuer: 'JPMorgan Chase',        coupon: '5.000%', maturity: '2031-03-01', size: '$3.0B', rating: 'A+',  spread: 'T+95' },
];

// --- Component ---------------------------------------------------------------

export default function FIDashboard() {
  // Fetch yield curve
  const { data: yieldData, isLoading: loadingYield } = useQuery<YieldTenor[]>({
    queryKey: ['fi', 'yield-curve'],
    queryFn: () => api.get('/v4/fi/yield-curve'),
    retry: 0,
  });
  const yieldCurve = yieldData ?? MOCK_YIELD_CURVE;

  // Fetch credit spreads
  const { data: creditData, isLoading: loadingCredit } = useQuery<CreditIndex[]>({
    queryKey: ['fi', 'credit-spreads'],
    queryFn: () => api.get('/v4/fi/credit-spreads'),
    retry: 0,
  });
  const creditMarket = creditData ?? MOCK_CREDIT;

  // Fetch recent issuance
  const { data: issuanceData, isLoading: loadingIssuance } = useQuery<RecentIssuance[]>({
    queryKey: ['fi', 'issuance'],
    queryFn: () => api.get('/v4/fi/issuance/recent'),
    retry: 0,
  });
  const recentIssuance = issuanceData ?? MOCK_ISSUANCE;

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
          Fixed Income Dashboard
        </h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          Yield curves, credit spreads, and new issuance
        </p>
      </div>

      {/* 2-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Yield Curve Table */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">US Treasury Yield Curve</h2>
            {loadingYield ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Array.from({ length: 11 }).map((_, i) => <Skeleton key={i} height="28px" />)}
              </div>
            ) : (
              <>
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>Tenor</th>
                      <th className="right">Yield</th>
                      <th className="right">1D Chg</th>
                      <th className="right">1W Chg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {yieldCurve.map((y) => (
                      <tr key={y.tenor}>
                        <td style={{ fontWeight: 500 }}>{y.tenor}</td>
                        <td className="right">{y.rate.toFixed(2)}%</td>
                        <td className="right" style={{ color: signalColor(y.change1d) }}>
                          {y.change1d >= 0 ? '+' : ''}{y.change1d.toFixed(2)}
                        </td>
                        <td className="right" style={{ color: signalColor(y.change1w) }}>
                          {y.change1w >= 0 ? '+' : ''}{y.change1w.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {/* Key spreads */}
                <div style={{ display: 'flex', gap: '24px', marginTop: '12px', paddingTop: '8px', borderTop: '1px solid var(--color-surface-border)' }}>
                  <div>
                    <span className="terminal-label">2s10s Spread: </span>
                    <span className="terminal-data" style={{ color: signalColor(-0.34) }}>-34 bps</span>
                  </div>
                  <div>
                    <span className="terminal-label">3m10y Spread: </span>
                    <span className="terminal-data" style={{ color: signalColor(-1.08) }}>-108 bps</span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Recent Issuance */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Recent Issuance</h2>
            {loadingIssuance ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height="28px" />)}
              </div>
            ) : (
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>Issuer</th>
                    <th className="right">Coupon</th>
                    <th className="right">Maturity</th>
                    <th className="right">Size</th>
                    <th className="right">Rating</th>
                    <th className="right">Spread</th>
                  </tr>
                </thead>
                <tbody>
                  {recentIssuance.map((bond, i) => (
                    <tr key={i}>
                      <td style={{ fontFamily: 'var(--font-ui)', whiteSpace: 'nowrap' }}>{bond.issuer}</td>
                      <td className="right">{bond.coupon}</td>
                      <td className="right" style={{ fontSize: 'var(--text-sm)' }}>{bond.maturity}</td>
                      <td className="right">{bond.size}</td>
                      <td className="right">{bond.rating}</td>
                      <td className="right" style={{ color: 'var(--color-signal-neutral)' }}>{bond.spread}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Credit Market */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Credit Market</h2>
            {loadingCredit ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height="48px" />)}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {creditMarket.map((c) => (
                  <div key={c.name} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{c.name}</span>
                      <span className="terminal-data" style={{ fontWeight: 600 }}>{c.oas} bps</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: signalColor(-c.change1d) }}>
                        {c.change1d >= 0 ? '+' : ''}{c.change1d} bps 1d
                      </span>
                      <span style={{
                        fontFamily: 'var(--font-ui)',
                        fontSize: 'var(--text-xs)',
                        padding: '1px 6px',
                        borderRadius: '2px',
                        color: regimeColor(c.regime),
                        background: `color-mix(in srgb, ${regimeColor(c.regime)} 15%, transparent)`,
                      }}>
                        {c.regime}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Links */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quick Links</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {['Treasury Dashboard', 'Credit Market Deep Dive', 'Bond Screener', 'Issuance Monitor'].map((label) => (
                <div
                  key={label}
                  style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--color-accent-primary)',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: 'var(--color-surface-raised)',
                  }}
                >
                  {label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
