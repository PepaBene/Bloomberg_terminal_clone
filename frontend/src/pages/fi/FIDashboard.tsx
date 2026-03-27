// ---------------------------------------------------------------------------
// Fixed Income Dashboard
// ---------------------------------------------------------------------------

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

interface YieldTenor {
  tenor: string;
  rate: number;
  change1d: number;
  change1w: number;
}

const yieldCurve: YieldTenor[] = [
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

const creditMarket: CreditIndex[] = [
  { name: 'IG Corporate OAS',  oas: 92,  change1d: -2, regime: 'Tight' },
  { name: 'HY Corporate OAS',  oas: 328, change1d: 4,  regime: 'Normal' },
  { name: 'IG Financial OAS',  oas: 78,  change1d: -1, regime: 'Tight' },
  { name: 'EM Sovereign OAS',  oas: 248, change1d: 3,  regime: 'Normal' },
];

function regimeColor(regime: string): string {
  switch (regime) {
    case 'Tight':   return 'var(--color-signal-positive)';
    case 'Normal':  return 'var(--color-signal-neutral)';
    case 'Wide':    return 'var(--color-signal-warning)';
    case 'Stress':  return 'var(--color-signal-negative)';
    default:        return 'var(--color-text-secondary)';
  }
}

interface RecentIssuance {
  issuer: string;
  coupon: string;
  maturity: string;
  size: string;
  rating: string;
  spread: string;
}

const recentIssuance: RecentIssuance[] = [
  { issuer: 'Apple Inc.',            coupon: '4.250%', maturity: '2034-03-15', size: '$3.0B', rating: 'AA+', spread: 'T+62' },
  { issuer: 'Goldman Sachs',         coupon: '5.125%', maturity: '2029-09-01', size: '$2.5B', rating: 'A-',  spread: 'T+108' },
  { issuer: 'Microsoft Corp.',       coupon: '4.000%', maturity: '2054-03-01', size: '$2.0B', rating: 'AAA', spread: 'T+55' },
  { issuer: 'Ford Motor Credit',     coupon: '5.750%', maturity: '2028-06-15', size: '$1.5B', rating: 'BBB-', spread: 'T+188' },
  { issuer: 'Amazon.com Inc.',       coupon: '4.125%', maturity: '2044-03-15', size: '$1.75B', rating: 'AA', spread: 'T+72' },
  { issuer: 'JPMorgan Chase',        coupon: '5.000%', maturity: '2031-03-01', size: '$3.0B', rating: 'A+',  spread: 'T+95' },
];

// --- Component ---------------------------------------------------------------

export default function FIDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Yield curves, credit spreads, and new issuance
        </p>
      </div>

      {/* 2-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Yield Curve Table */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>US Treasury Yield Curve</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Tenor', 'Yield', '1D Chg', '1W Chg'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Tenor' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {yieldCurve.map((y) => (
                  <tr key={y.tenor} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{y.tenor}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{y.rate.toFixed(2)}%</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(y.change1d) }}>
                      {y.change1d >= 0 ? '+' : ''}{y.change1d.toFixed(2)}
                    </td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(y.change1w) }}>
                      {y.change1w >= 0 ? '+' : ''}{y.change1w.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Key spreads */}
            <div style={{ display: 'flex', gap: '24px', marginTop: '12px', paddingTop: '8px', borderTop: '1px solid var(--color-surface-border)' }}>
              <div>
                <span style={labelStyle}>2s10s Spread: </span>
                <span style={{ ...dataStyle, color: signalColor(-0.34) }}>-34 bps</span>
              </div>
              <div>
                <span style={labelStyle}>3m10y Spread: </span>
                <span style={{ ...dataStyle, color: signalColor(-1.08) }}>-108 bps</span>
              </div>
            </div>
          </div>

          {/* Recent Issuance */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Recent Issuance</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Issuer', 'Coupon', 'Maturity', 'Size', 'Rating', 'Spread'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentIssuance.map((bond, i) => (
                  <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{bond.issuer}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{bond.coupon}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{bond.maturity}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{bond.size}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{bond.rating}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-signal-neutral)' }}>{bond.spread}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Credit Market */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Credit Market</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {creditMarket.map((c) => (
                <div key={c.name} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)' }}>{c.name}</span>
                    <span style={{ ...dataStyle, fontWeight: 600 }}>{c.oas} bps</span>
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
          </div>

          {/* Quick Links */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Quick Links</h2>
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
