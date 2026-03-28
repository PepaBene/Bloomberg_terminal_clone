// ---------------------------------------------------------------------------
// Valuation Dashboard — DCF Inputs, Multiples, Peer Valuation
// ---------------------------------------------------------------------------
import { RatioDashboard } from '@/components/company/RatioDashboard';
import type { DuPontData, MultiplesPoint } from '@/components/company/RatioDashboard';

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

const company = { name: 'Apple Inc.', ticker: 'AAPL', price: 178.72 };

const dcfInputs = [
  { param: 'Revenue Growth (5Y CAGR)', value: '6.2%' },
  { param: 'Terminal Growth Rate', value: '2.5%' },
  { param: 'WACC', value: '9.8%' },
  { param: 'EBITDA Margin (Terminal)', value: '33.5%' },
  { param: 'CapEx / Revenue', value: '2.8%' },
  { param: 'Tax Rate', value: '16.2%' },
];

const dcfOutputs = [
  { scenario: 'Bear Case', evTarget: 2250, impliedPrice: 146.12, upside: -18.2 },
  { scenario: 'Base Case', evTarget: 2780, impliedPrice: 180.53, upside: 1.0 },
  { scenario: 'Bull Case', evTarget: 3420, impliedPrice: 222.08, upside: 24.2 },
];

const peerValuation = [
  { ticker: 'AAPL', name: 'Apple', pe: 28.6, evEbitda: 22.1, pfcf: 25.7, evRev: 7.4, mktCap: '2.78T' },
  { ticker: 'MSFT', name: 'Microsoft', pe: 34.2, evEbitda: 24.8, pfcf: 33.1, evRev: 12.8, mktCap: '3.12T' },
  { ticker: 'GOOGL', name: 'Alphabet', pe: 24.5, evEbitda: 16.2, pfcf: 28.4, evRev: 6.1, mktCap: '2.05T' },
  { ticker: 'AMZN', name: 'Amazon', pe: 58.3, evEbitda: 18.9, pfcf: 42.7, evRev: 3.2, mktCap: '1.92T' },
  { ticker: 'META', name: 'Meta', pe: 22.8, evEbitda: 14.5, pfcf: 20.1, evRev: 8.7, mktCap: '1.28T' },
];

// RatioDashboard mock data
const dupontData: DuPontData = {
  roe: 1.37,
  profitMargin: 0.26,
  assetTurnover: 1.11,
  equityMultiplier: 4.76,
};

const multiplesHistory: MultiplesPoint[] = [
  { period: '2018', pe: 14.5, evEbitda: 10.8, pbv: 8.2 },
  { period: '2019', pe: 20.3, evEbitda: 15.2, pbv: 13.5 },
  { period: '2020', pe: 35.2, evEbitda: 26.4, pbv: 28.7 },
  { period: '2021', pe: 28.8, evEbitda: 22.1, pbv: 35.6 },
  { period: '2022', pe: 22.4, evEbitda: 18.5, pbv: 42.1 },
  { period: '2023', pe: 26.1, evEbitda: 20.2, pbv: 48.3 },
  { period: '2024', pe: 27.5, evEbitda: 21.0, pbv: 44.8 },
  { period: '2025', pe: 28.6, evEbitda: 22.1, pbv: 45.2 },
];

// --- Component ---------------------------------------------------------------

export default function ValuationDashboard() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Valuation Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{company.ticker} &mdash; {company.name} &mdash; ${company.price.toFixed(2)}</p>
      </div>

      {/* DuPont Decomposition + Multiples History via RatioDashboard */}
      <div style={{ marginBottom: 'var(--panel-gap)' }}>
        <RatioDashboard dupont={dupontData} multiplesHistory={multiplesHistory} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* DCF Inputs */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>DCF Model Inputs</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {dcfInputs.map((d) => (
                <tr key={d.param} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...labelStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.param}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{d.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* DCF Scenarios */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>DCF Scenario Analysis</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Scenario', 'EV ($T)', 'Implied Price', 'Upside'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Scenario' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dcfOutputs.map((d) => (
                <tr key={d.scenario} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.scenario}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${(d.evTarget / 1000).toFixed(2)}T</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>${d.impliedPrice.toFixed(2)}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(d.upside), fontWeight: 600 }}>
                    {d.upside >= 0 ? '+' : ''}{d.upside.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Peer Valuation */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Peer Valuation</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Ticker', 'P/E', 'EV/EBITDA', 'P/FCF', 'EV/Rev', 'Mkt Cap'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Ticker' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {peerValuation.map((p) => (
                <tr key={p.ticker} style={{ height: 'var(--table-row-height)', background: p.ticker === 'AAPL' ? 'var(--color-surface-overlay)' : 'transparent' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)' }}>{p.ticker}</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.pe.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.evEbitda.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.pfcf.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{p.evRev.toFixed(1)}x</td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>${p.mktCap}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
