// ---------------------------------------------------------------------------
// Fixed Income Dashboard
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { YieldCurveChart } from '@/components/charts';
import type { YieldCurvePoint } from '@/components/charts';
import { KeySpreadsPanel, NewIssueTable } from '@/components/fi';
import type { SpreadRow, NewIssue } from '@/components/fi';

// --- Helpers -----------------------------------------------------------------

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
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

// --- Yield Curve Chart Data --------------------------------------------------

const CURRENT_CURVE: YieldCurvePoint[] = [
  { tenor: '1M', rate: 5.38 }, { tenor: '3M', rate: 5.36 }, { tenor: '6M', rate: 5.27 },
  { tenor: '1Y', rate: 5.02 }, { tenor: '2Y', rate: 4.62 }, { tenor: '3Y', rate: 4.42 },
  { tenor: '5Y', rate: 4.28 }, { tenor: '7Y', rate: 4.30 }, { tenor: '10Y', rate: 4.28 },
  { tenor: '20Y', rate: 4.52 }, { tenor: '30Y', rate: 4.42 },
];

const PRIOR_CURVE: YieldCurvePoint[] = [
  { tenor: '1M', rate: 5.40 }, { tenor: '3M', rate: 5.39 }, { tenor: '6M', rate: 5.32 },
  { tenor: '1Y', rate: 5.10 }, { tenor: '2Y', rate: 4.74 }, { tenor: '3Y', rate: 4.52 },
  { tenor: '5Y', rate: 4.36 }, { tenor: '7Y', rate: 4.36 }, { tenor: '10Y', rate: 4.35 },
  { tenor: '20Y', rate: 4.56 }, { tenor: '30Y', rate: 4.47 },
];

// --- KeySpreadsPanel data ----------------------------------------------------

const KEY_SPREADS: SpreadRow[] = [
  { name: 'IG OAS',         value: 92,  change1d: -2, change1w: -5, percentile: 22 },
  { name: 'HY OAS',         value: 328, change1d: 4,  change1w: -8, percentile: 35 },
  { name: 'BBB-BB Spread',  value: 182, change1d: 1,  change1w: -4, percentile: 28 },
  { name: '2s10s',          value: -34, change1d: 1,  change1w: 3,  percentile: 15 },
  { name: '3m10y',          value: -108, change1d: 2,  change1w: 5,  percentile: 8 },
];

// --- NewIssueTable data ------------------------------------------------------

const NEW_ISSUES: NewIssue[] = [
  { issuer: 'Apple Inc.',        coupon: 4.250, maturity: '2034-03-15', size: '$3.0B', rating: 'AA+',  spread: 62,  initialTalk: 65, status: 'priced' },
  { issuer: 'Goldman Sachs',     coupon: 5.125, maturity: '2029-09-01', size: '$2.5B', rating: 'A-',   spread: 108, initialTalk: 115, status: 'priced' },
  { issuer: 'Microsoft Corp.',   coupon: 4.000, maturity: '2054-03-01', size: '$2.0B', rating: 'AAA',  spread: 55,  initialTalk: 60, status: 'priced' },
  { issuer: 'Ford Motor Credit', coupon: 5.750, maturity: '2028-06-15', size: '$1.5B', rating: 'BBB-', spread: 188, initialTalk: 195, status: 'priced' },
  { issuer: 'Amazon.com Inc.',   coupon: 4.125, maturity: '2044-03-15', size: '$1.75B', rating: 'AA',  spread: 72,  initialTalk: 78, status: 'launched' },
  { issuer: 'JPMorgan Chase',    coupon: 5.000, maturity: '2031-03-01', size: '$3.0B', rating: 'A+',   spread: 95,  initialTalk: 100, status: 'upcoming' },
];

// --- Component ---------------------------------------------------------------

const QUICK_LINK_ROUTES: Record<string, string> = {
  'Treasury Dashboard': '/fi/treasuries',
  'Credit Market Deep Dive': '/fi/credit',
  'Bond Screener': '/screener/fi',
  'Issuance Monitor': '/fi/issuance',
};

export default function FIDashboard() {
  const navigate = useNavigate();

  // Fetch yield curve
  const { data: yieldData, isLoading: loadingYield } = useQuery<YieldTenor[]>({
    queryKey: ['fi', 'yield-curve'],
    queryFn: () => api.get('/v4/fi/yield-curve'),
    retry: 0,
  });
  const yieldCurve = yieldData ?? MOCK_YIELD_CURVE;

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

          {/* Yield Curve Chart */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Yield Curve (Current vs 1W Ago)</h2>
            <YieldCurveChart
              current={CURRENT_CURVE}
              prior={PRIOR_CURVE}
              priorLabel="1 Week Ago"
              height={250}
            />
          </div>

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
              </>
            )}
          </div>

          {/* NewIssueTable replaces inline issuance table */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Recent Issuance</h2>
            <NewIssueTable issues={NEW_ISSUES} />
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* KeySpreadsPanel */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Key Spreads</h2>
            <KeySpreadsPanel spreads={KEY_SPREADS} />
          </div>

          {/* Quick Links */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quick Links</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {['Treasury Dashboard', 'Credit Market Deep Dive', 'Bond Screener', 'Issuance Monitor'].map((label) => (
                <div
                  key={label}
                  onClick={() => navigate(QUICK_LINK_ROUTES[label])}
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
