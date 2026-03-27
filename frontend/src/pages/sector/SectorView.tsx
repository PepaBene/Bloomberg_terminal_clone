// ---------------------------------------------------------------------------
// Sector View — 11 GICS Sectors with Performance Metrics
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

function signalColor(v: number): string {
  return v >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

// --- Mock Data ---------------------------------------------------------------

const sectors = [
  { name: 'Information Technology', etf: 'XLK', weight: 31.2, d1: 0.82, wtd: 1.45, mtd: 3.21, ytd: 12.8, pe: 30.2, relPE: 1.15 },
  { name: 'Health Care', etf: 'XLV', weight: 12.8, d1: -0.34, wtd: -0.12, mtd: 1.05, ytd: 4.2, pe: 18.5, relPE: 0.71 },
  { name: 'Financials', etf: 'XLF', weight: 13.1, d1: 0.15, wtd: 0.68, mtd: 2.10, ytd: 8.5, pe: 14.8, relPE: 0.56 },
  { name: 'Consumer Discretionary', etf: 'XLY', weight: 10.5, d1: 0.45, wtd: 1.02, mtd: 2.85, ytd: 9.1, pe: 25.4, relPE: 0.97 },
  { name: 'Communication Services', etf: 'XLC', weight: 8.9, d1: 0.62, wtd: 1.28, mtd: 3.45, ytd: 11.2, pe: 22.1, relPE: 0.84 },
  { name: 'Industrials', etf: 'XLI', weight: 8.4, d1: -0.21, wtd: 0.35, mtd: 1.82, ytd: 6.8, pe: 21.5, relPE: 0.82 },
  { name: 'Consumer Staples', etf: 'XLP', weight: 5.8, d1: -0.52, wtd: -0.78, mtd: -0.45, ytd: -1.2, pe: 21.8, relPE: 0.83 },
  { name: 'Energy', etf: 'XLE', weight: 3.7, d1: 1.15, wtd: 2.35, mtd: 4.12, ytd: -3.5, pe: 11.2, relPE: 0.43 },
  { name: 'Utilities', etf: 'XLU', weight: 2.5, d1: -0.18, wtd: -0.42, mtd: 0.32, ytd: 2.1, pe: 17.2, relPE: 0.66 },
  { name: 'Real Estate', etf: 'XLRE', weight: 2.3, d1: -0.68, wtd: -1.15, mtd: -1.85, ytd: -4.8, pe: 35.2, relPE: 1.34 },
  { name: 'Materials', etf: 'XLB', weight: 2.2, d1: 0.28, wtd: 0.55, mtd: 1.42, ytd: 3.8, pe: 18.8, relPE: 0.72 },
];

const marketBreadth = [
  { label: 'S&P 500', value: '5,248.72' },
  { label: 'Advancing', value: '312' },
  { label: 'Declining', value: '185' },
  { label: 'New Highs', value: '42' },
  { label: 'New Lows', value: '8' },
  { label: 'A/D Ratio', value: '1.69' },
];

// --- Component ---------------------------------------------------------------

export default function SectorView() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Sector Performance
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>GICS sector performance, valuation, and market breadth</p>
      </div>

      {/* Breadth KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {marketBreadth.map((m) => (
          <div key={m.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{m.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Sector Table */}
      <div style={panelStyle}>
        <h2 style={sectionTitle}>GICS Sector Overview</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Sector', 'ETF', 'Wt %', '1D %', 'WTD %', 'MTD %', 'YTD %', 'P/E', 'Rel P/E'].map((h) => (
                <th key={h} style={{ ...labelStyle, textAlign: ['Sector', 'ETF'].includes(h) ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sectors.map((s) => (
              <tr key={s.name} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{s.name}</td>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{s.etf}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.weight.toFixed(1)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.d1) }}>{s.d1 >= 0 ? '+' : ''}{s.d1.toFixed(2)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.wtd) }}>{s.wtd >= 0 ? '+' : ''}{s.wtd.toFixed(2)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.mtd) }}>{s.mtd >= 0 ? '+' : ''}{s.mtd.toFixed(2)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(s.ytd), fontWeight: 500 }}>{s.ytd >= 0 ? '+' : ''}{s.ytd.toFixed(1)}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{s.pe.toFixed(1)}x</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: s.relPE > 1 ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)' }}>{s.relPE.toFixed(2)}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
