// ---------------------------------------------------------------------------
// Fixed Income Dashboard
// ---------------------------------------------------------------------------
import { useNavigate } from 'react-router-dom';
import { useYieldCurve, useCreditSpreads, useNewIssuance, useFIBriefing, useAgencyBonds } from '@/hooks';
import { YieldCurveChart } from '@/components/charts';
import type { YieldCurvePoint } from '@/components/charts';
import { KeySpreadsPanel, NewIssueTable } from '@/components/fi';
import type { SpreadRow, NewIssue } from '@/components/fi';

// --- API response shapes ----------------------------------------------------
// [P1-FP-018 note] Unlike the other pages cleaned up alongside this one,
// none of `/v1/fi/yield-curve`, `/v1/fi/credit/sector-spreads`,
// `/v1/fi/new-issues`, or `/v1/fi/agency` (the endpoints these hooks call)
// match any route actually defined under `src/api/routers/` — the real FI
// routers are mounted at `/v1/fixed-income/...` (`fi_yield_curve.py`) and a
// differently-shaped `/v1/fi/...` intelligence domain (`fi_intelligence.py`,
// e.g. `/fi/credit/briefing`, `/fi/yield-curve/history`). That's a separate,
// systemic path-mismatch issue across the whole Fixed Income domain — out of
// scope for this cleanup pass. These types describe the shape the UI needs
// (matching `KeySpreadsPanel`/`NewIssueTable`'s own prop types) with a
// runtime `Array.isArray` guard, since the real response contract can't be
// confirmed against a live route today.
interface AgencyBondApi {
  issuer: string;
  coupon: number | string;
  maturity: string;
  size: string;
  spread: number;
  rating: string;
}

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

// --- Default empty data (populated by API) -----------------------------------

interface YieldTenor {
  tenor: string;
  rate: number;
  change1d: number;
  change1w: number;
}

const MOCK_YIELD_CURVE: YieldTenor[] = [];

const CURRENT_CURVE: YieldCurvePoint[] = [];

const PRIOR_CURVE: YieldCurvePoint[] = [];

const KEY_SPREADS: SpreadRow[] = [];

const NEW_ISSUES: NewIssue[] = [];

const MOCK_AGENCY_BONDS: AgencyBondApi[] = [];

// --- Component ---------------------------------------------------------------

const QUICK_LINK_ROUTES: Record<string, string> = {
  'Treasury Dashboard': '/fi/treasuries',
  'Credit Market Deep Dive': '/fi/credit',
  'Bond Screener': '/screener/fi',
  'Issuance Monitor': '/fi/issuance',
};

export default function FIDashboard() {
  const navigate = useNavigate();

  // Fetch data via hooks (with mock fallbacks)
  const { data: apiYield, isLoading: loadingYield } = useYieldCurve();
  const { data: apiSpreads } = useCreditSpreads();
  const { data: apiNewIssues } = useNewIssuance();
  const { data: apiBriefing } = useFIBriefing();
  const { data: apiAgency } = useAgencyBonds();

  const yieldCurve: YieldTenor[] = Array.isArray(apiYield) ? (apiYield as YieldTenor[]) : MOCK_YIELD_CURVE;
  const spreads: SpreadRow[] = Array.isArray((apiSpreads as { spreads?: unknown } | undefined)?.spreads)
    ? ((apiSpreads as { spreads: SpreadRow[] }).spreads)
    : KEY_SPREADS;
  const newIssues: NewIssue[] = Array.isArray(apiNewIssues) ? (apiNewIssues as NewIssue[]) : NEW_ISSUES;
  const agencyBonds: AgencyBondApi[] = Array.isArray(apiAgency) ? (apiAgency as AgencyBondApi[]) : MOCK_AGENCY_BONDS;

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
            <NewIssueTable issues={newIssues} />
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* KeySpreadsPanel */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Key Spreads</h2>
            <KeySpreadsPanel spreads={spreads} />
          </div>

          {/* Quick Links */}
          <div className="terminal-panel">
            <h2 className="terminal-section-title">Quick Links</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {['Treasury Dashboard', 'Credit Market Deep Dive', 'Bond Screener', 'Issuance Monitor'].map((label) => (
                <div
                  key={label}
                  onClick={() => {
                    const route = QUICK_LINK_ROUTES[label];
                    if (route) navigate(route);
                  }}
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

      {/* AI Market Narrative */}
      {(() => {
        const MOCK_BRIEFING = '';
        const briefing = apiBriefing as { text?: string; narrative?: string } | undefined;
        const briefingText = briefing?.text ?? briefing?.narrative ?? MOCK_BRIEFING;
        return briefingText ? (
          <div className="terminal-panel" style={{ marginTop: 'var(--panel-gap)' }}>
            <h2 className="terminal-section-title">AI Market Narrative</h2>
            <p
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                lineHeight: 1.6,
                color: 'var(--color-text-primary)',
                margin: 0,
              }}
            >
              {briefingText}
            </p>
          </div>
        ) : null;
      })()}

      {/* Agency Bonds */}
      <div className="terminal-panel" style={{ marginTop: 'var(--panel-gap)' }}>
        <h2 className="terminal-section-title">Agency Bonds</h2>
        <table className="terminal-table">
          <thead>
            <tr>
              <th>Issuer</th>
              <th className="right">Coupon</th>
              <th className="right">Maturity</th>
              <th className="right">Size</th>
              <th className="right">Spread (bps)</th>
              <th className="right">Rating</th>
            </tr>
          </thead>
          <tbody>
            {agencyBonds.map((b, i: number) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{b.issuer}</td>
                <td className="right">{Number(b.coupon).toFixed(3)}%</td>
                <td className="right">{b.maturity}</td>
                <td className="right">{b.size}</td>
                <td className="right">+{b.spread}</td>
                <td className="right" style={{ color: 'var(--color-signal-positive)' }}>{b.rating}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
