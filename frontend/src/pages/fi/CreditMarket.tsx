// ---------------------------------------------------------------------------
// Credit Market — IG/HY Spread Indices, Credit Regime, Sector Spreads
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

function chgColor(v: number): string {
  return v <= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const spreadIndices = [
  { index: 'CDX IG', spread: 52, chg1d: -1, chg1w: -3, chg1m: -8, pctile: 22 },
  { index: 'CDX HY', spread: 328, chg1d: 2, chg1w: -5, chg1m: -18, pctile: 35 },
  { index: 'iTraxx Main', spread: 55, chg1d: 0, chg1w: -2, chg1m: -6, pctile: 25 },
  { index: 'iTraxx Xover', spread: 295, chg1d: -3, chg1w: -8, chg1m: -22, pctile: 30 },
];

const creditRegime = [
  { label: 'Current Regime', value: 'Risk-On' },
  { label: 'IG Spread Pctile (5Y)', value: '22nd' },
  { label: 'HY Spread Pctile (5Y)', value: '35th' },
  { label: 'IG Default Rate (LTM)', value: '0.05%' },
  { label: 'HY Default Rate (LTM)', value: '2.8%' },
  { label: 'Distressed Ratio', value: '4.2%' },
];

const sectorSpreads = [
  { sector: 'Technology', igOas: 45, hyOas: 285, chg1m: -12 },
  { sector: 'Healthcare', igOas: 62, hyOas: 310, chg1m: -8 },
  { sector: 'Financials', igOas: 58, hyOas: 295, chg1m: -5 },
  { sector: 'Energy', igOas: 72, hyOas: 365, chg1m: 8 },
  { sector: 'Consumer', igOas: 55, hyOas: 305, chg1m: -10 },
  { sector: 'Industrials', igOas: 60, hyOas: 320, chg1m: -6 },
  { sector: 'Utilities', igOas: 68, hyOas: 275, chg1m: -3 },
];

// --- Component ---------------------------------------------------------------

export default function CreditMarket() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Credit Market Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>IG &amp; HY spread indices, credit regime, and sector analysis</p>
      </div>

      {/* Regime KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {creditRegime.map((r) => (
          <div key={r.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{r.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: r.value === 'Risk-On' ? 'var(--color-signal-positive)' : 'var(--color-text-primary)' }}>{r.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Spread Indices */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Credit Indices (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Index', 'Spread', '1D', '1W', '1M', 'Pctile'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Index' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spreadIndices.map((s) => (
                <tr key={s.index} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.index}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{s.spread}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1d) }}>{s.chg1d > 0 ? '+' : ''}{s.chg1d}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1w) }}>{s.chg1w > 0 ? '+' : ''}{s.chg1w}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1m) }}>{s.chg1m > 0 ? '+' : ''}{s.chg1m}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{s.pctile}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Sector Spreads */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Sector Spreads (bps)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Sector', 'IG OAS', 'HY OAS', '1M Chg'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Sector' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sectorSpreads.map((s) => (
                <tr key={s.sector} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.sector}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.igOas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.hyOas}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: chgColor(s.chg1m) }}>{s.chg1m > 0 ? '+' : ''}{s.chg1m}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
