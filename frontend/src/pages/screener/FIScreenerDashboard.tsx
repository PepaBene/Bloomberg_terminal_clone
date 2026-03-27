// ---------------------------------------------------------------------------
// Fixed Income Screener Dashboard
// ---------------------------------------------------------------------------
import { useState } from 'react';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
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

const selectStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: '4px 8px',
  outline: 'none',
};

const inputStyle: React.CSSProperties = {
  ...selectStyle,
  width: '72px',
  fontFamily: 'var(--font-data)',
};

function spreadColor(oas: number): string {
  if (oas >= 200) return 'var(--color-signal-negative)';
  if (oas >= 120) return 'var(--color-quality-2)';
  return 'var(--color-text-primary)';
}

function yieldColor(ytm: number): string {
  if (ytm >= 6) return 'var(--color-signal-positive)';
  if (ytm >= 5) return 'var(--color-quality-4)';
  return 'var(--color-text-primary)';
}

// --- Mock Data ---------------------------------------------------------------

interface BondRow {
  cusip: string;
  issuer: string;
  coupon: number;
  maturity: string;
  rating: string;
  ratingCategory: 'IG' | 'HY';
  sector: string;
  maturityBucket: string;
  oas: number;
  ytm: number;
  price: number;
}

const mockBonds: BondRow[] = [
  { cusip: '037833100', issuer: 'Apple Inc.',        coupon: 4.125, maturity: '2028-05-15', rating: 'AA+', ratingCategory: 'IG', sector: 'Technology', maturityBucket: '3-5Y', oas: 52,  ytm: 4.68,  price: 98.42 },
  { cusip: '594918104', issuer: 'Microsoft Corp.',   coupon: 3.750, maturity: '2027-08-08', rating: 'AAA', ratingCategory: 'IG', sector: 'Technology', maturityBucket: '1-3Y', oas: 38,  ytm: 4.32,  price: 99.18 },
  { cusip: '46625H100', issuer: 'JPMorgan Chase',    coupon: 5.250, maturity: '2033-01-15', rating: 'A+',  ratingCategory: 'IG', sector: 'Financials', maturityBucket: '5-10Y', oas: 95,  ytm: 5.42,  price: 101.24 },
  { cusip: '38141G104', issuer: 'Goldman Sachs',     coupon: 5.750, maturity: '2034-10-01', rating: 'A',   ratingCategory: 'IG', sector: 'Financials', maturityBucket: '5-10Y', oas: 118, ytm: 5.88,  price: 99.86 },
  { cusip: '172967424', issuer: 'Citigroup Inc.',    coupon: 6.125, maturity: '2036-07-15', rating: 'BBB+', ratingCategory: 'IG', sector: 'Financials', maturityBucket: '10+Y', oas: 142, ytm: 6.18,  price: 97.62 },
  { cusip: '345370860', issuer: 'Ford Motor Co.',    coupon: 6.625, maturity: '2028-02-15', rating: 'BB+', ratingCategory: 'HY', sector: 'Consumer Disc.', maturityBucket: '1-3Y', oas: 225, ytm: 6.84,  price: 100.52 },
  { cusip: '120568AE5', issuer: 'T-Mobile US',      coupon: 5.375, maturity: '2031-04-15', rating: 'BBB', ratingCategory: 'IG', sector: 'Telecom',    maturityBucket: '5-10Y', oas: 108, ytm: 5.52,  price: 98.94 },
  { cusip: '26884LAC8', issuer: 'Energy Transfer',   coupon: 7.125, maturity: '2029-08-01', rating: 'BB',  ratingCategory: 'HY', sector: 'Energy',     maturityBucket: '3-5Y', oas: 268, ytm: 7.34,  price: 99.28 },
];

const sectors = ['All', 'Technology', 'Financials', 'Consumer Disc.', 'Telecom', 'Energy'];
const maturityBuckets = ['All', '1-3Y', '3-5Y', '5-10Y', '10+Y'];

// --- Component ---------------------------------------------------------------

export default function FIScreenerDashboard() {
  const [ratingFilter, setRatingFilter] = useState('All');
  const [maturityFilter, setMaturityFilter] = useState('All');
  const [sectorFilter, setSectorFilter] = useState('All');
  const [minYield, setMinYield] = useState('');

  const filtered = mockBonds.filter((b) => {
    if (ratingFilter === 'IG' && b.ratingCategory !== 'IG') return false;
    if (ratingFilter === 'HY' && b.ratingCategory !== 'HY') return false;
    if (maturityFilter !== 'All' && b.maturityBucket !== maturityFilter) return false;
    if (sectorFilter !== 'All' && b.sector !== sectorFilter) return false;
    if (minYield && b.ytm < Number(minYield)) return false;
    return true;
  });

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Screener
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {filtered.length} bonds matching filters
        </p>
      </div>

      {/* Filter Bar */}
      <div style={{
        ...panelStyle,
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        flexWrap: 'wrap',
        marginBottom: 'var(--panel-gap)',
        padding: '8px 12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Rating</span>
          <select style={selectStyle} value={ratingFilter} onChange={(e) => setRatingFilter(e.target.value)}>
            <option value="All">All</option>
            <option value="IG">Investment Grade</option>
            <option value="HY">High Yield</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Maturity</span>
          <select style={selectStyle} value={maturityFilter} onChange={(e) => setMaturityFilter(e.target.value)}>
            {maturityBuckets.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Sector</span>
          <select style={selectStyle} value={sectorFilter} onChange={(e) => setSectorFilter(e.target.value)}>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={labelStyle}>Min Yield</span>
          <input style={inputStyle} placeholder="%" value={minYield} onChange={(e) => setMinYield(e.target.value)} />
        </div>
      </div>

      {/* Results Table */}
      <div style={panelStyle}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['CUSIP', 'Issuer', 'Coupon', 'Maturity', 'Rating', 'OAS (bps)', 'YTM', 'Price'].map((h) => (
                <th
                  key={h}
                  style={{
                    ...labelStyle,
                    textAlign: h === 'CUSIP' || h === 'Issuer' || h === 'Rating' ? 'left' : 'right',
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((b) => (
              <tr key={b.cusip} style={{ height: 'var(--table-row-height)' }}>
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600, color: 'var(--color-accent-primary)', fontSize: 'var(--text-sm)' }}>{b.cusip}</td>
                <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{b.issuer}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.coupon.toFixed(3)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{b.maturity}</td>
                <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={{
                    fontFamily: 'var(--font-ui)',
                    fontSize: 'var(--text-xs)',
                    padding: '1px 6px',
                    borderRadius: '2px',
                    color: b.ratingCategory === 'IG' ? 'var(--color-quality-5)' : 'var(--color-quality-2)',
                    background: b.ratingCategory === 'IG'
                      ? 'color-mix(in srgb, var(--color-quality-5) 15%, transparent)'
                      : 'color-mix(in srgb, var(--color-quality-2) 15%, transparent)',
                  }}>
                    {b.rating}
                  </span>
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: spreadColor(b.oas), fontWeight: 600 }}>{b.oas}</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: yieldColor(b.ytm), fontWeight: 600 }}>{b.ytm.toFixed(2)}%</td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{b.price.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
