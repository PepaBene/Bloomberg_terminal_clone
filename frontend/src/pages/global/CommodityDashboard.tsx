// ---------------------------------------------------------------------------
// Commodity Dashboard
// ---------------------------------------------------------------------------
import { useState, useMemo } from 'react';
import { CommodityPriceChart } from '@/components/global';
import type { CommodityPricePoint } from '@/components/global';

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

function percentileColor(pct: number): string {
  if (pct >= 80) return 'var(--color-signal-negative)';
  if (pct >= 60) return 'var(--color-quality-2)';
  if (pct >= 40) return 'var(--color-signal-neutral)';
  if (pct >= 20) return 'var(--color-quality-4)';
  return 'var(--color-signal-positive)';
}

// --- Mock Data ---------------------------------------------------------------

type CommodityCategory = 'Energy' | 'Precious Metals' | 'Industrial Metals' | 'Agriculture';

interface CommodityRow {
  name: string;
  code: string;
  category: CommodityCategory;
  price: number;
  unit: string;
  change1d: number;
  change1w: number;
  change1m: number;
  changeYtd: number;
  percentile1y: number;
}

const commodities: CommodityRow[] = [
  { name: 'WTI Crude Oil',  code: 'CL',  category: 'Energy',            price: 78.42,    unit: '$/bbl',    change1d: -0.84, change1w: 1.24,  change1m: -3.42, changeYtd: 8.62,   percentile1y: 58 },
  { name: 'Brent Crude',    code: 'CO',  category: 'Energy',            price: 82.18,    unit: '$/bbl',    change1d: -0.62, change1w: 0.98,  change1m: -2.86, changeYtd: 7.84,   percentile1y: 62 },
  { name: 'Natural Gas',    code: 'NG',  category: 'Energy',            price: 1.92,     unit: '$/MMBtu',  change1d: -2.42, change1w: -4.18, change1m: -12.6, changeYtd: -28.4,  percentile1y: 12 },
  { name: 'Gold',           code: 'XAU', category: 'Precious Metals',   price: 2341.80,  unit: '$/oz',     change1d: 0.38,  change1w: 1.82,  change1m: 4.24,  changeYtd: 12.68,  percentile1y: 92 },
  { name: 'Silver',         code: 'XAG', category: 'Precious Metals',   price: 28.64,    unit: '$/oz',     change1d: 0.82,  change1w: 2.46,  change1m: 6.12,  changeYtd: 18.42,  percentile1y: 85 },
  { name: 'Platinum',       code: 'XPT', category: 'Precious Metals',   price: 1024.50,  unit: '$/oz',     change1d: -0.24, change1w: -0.86, change1m: 2.14,  changeYtd: 5.82,   percentile1y: 55 },
  { name: 'Copper',         code: 'HG',  category: 'Industrial Metals', price: 4.12,     unit: '$/lb',     change1d: 1.18,  change1w: 2.84,  change1m: 5.62,  changeYtd: 9.24,   percentile1y: 78 },
  { name: 'Aluminum',       code: 'AL',  category: 'Industrial Metals', price: 2418.00,  unit: '$/mt',     change1d: 0.42,  change1w: 1.28,  change1m: 3.46,  changeYtd: 6.82,   percentile1y: 64 },
  { name: 'Iron Ore',       code: 'FE',  category: 'Industrial Metals', price: 108.24,   unit: '$/mt',     change1d: -1.62, change1w: -2.84, change1m: -8.42, changeYtd: -14.28, percentile1y: 28 },
  { name: 'Wheat',          code: 'ZW',  category: 'Agriculture',       price: 5.87,     unit: '$/bu',     change1d: 0.62,  change1w: -0.42, change1m: -2.18, changeYtd: -8.62,  percentile1y: 32 },
  { name: 'Corn',           code: 'ZC',  category: 'Agriculture',       price: 4.42,     unit: '$/bu',     change1d: 0.28,  change1w: 0.86,  change1m: 1.24,  changeYtd: -4.28,  percentile1y: 38 },
  { name: 'Soybeans',       code: 'ZS',  category: 'Agriculture',       price: 11.84,    unit: '$/bu',     change1d: -0.48, change1w: -1.24, change1m: -3.62, changeYtd: -6.84,  percentile1y: 24 },
];

interface ExposedCompany {
  ticker: string;
  name: string;
  exposure: string;
}

const exposureMap: Record<CommodityCategory, ExposedCompany[]> = {
  'Energy': [
    { ticker: 'XOM',  name: 'Exxon Mobil',       exposure: 'Direct Producer' },
    { ticker: 'CVX',  name: 'Chevron Corp.',      exposure: 'Direct Producer' },
    { ticker: 'COP',  name: 'ConocoPhillips',     exposure: 'Direct Producer' },
    { ticker: 'SLB',  name: 'Schlumberger',       exposure: 'Services' },
    { ticker: 'DAL',  name: 'Delta Air Lines',    exposure: 'Cost Exposure' },
  ],
  'Precious Metals': [
    { ticker: 'NEM',  name: 'Newmont Corp.',      exposure: 'Gold Miner' },
    { ticker: 'GOLD', name: 'Barrick Gold',       exposure: 'Gold Miner' },
    { ticker: 'WPM',  name: 'Wheaton Prec. Met.', exposure: 'Streaming' },
    { ticker: 'FNV',  name: 'Franco-Nevada',      exposure: 'Royalty' },
    { ticker: 'AEM',  name: 'Agnico Eagle',       exposure: 'Gold Miner' },
  ],
  'Industrial Metals': [
    { ticker: 'FCX',  name: 'Freeport-McMoRan',   exposure: 'Copper Mining' },
    { ticker: 'BHP',  name: 'BHP Group',          exposure: 'Diversified Mining' },
    { ticker: 'RIO',  name: 'Rio Tinto',          exposure: 'Iron/Aluminum' },
    { ticker: 'VALE', name: 'Vale S.A.',          exposure: 'Iron Ore' },
    { ticker: 'AA',   name: 'Alcoa Corp.',        exposure: 'Aluminum' },
  ],
  'Agriculture': [
    { ticker: 'ADM',  name: 'Archer-Daniels',     exposure: 'Processing' },
    { ticker: 'BG',   name: 'Bunge Global',       exposure: 'Trading' },
    { ticker: 'CTVA', name: 'Corteva Inc.',       exposure: 'Ag Chemicals' },
    { ticker: 'DE',   name: 'Deere & Co.',        exposure: 'Equipment' },
    { ticker: 'MOS',  name: 'Mosaic Co.',         exposure: 'Fertilizer' },
  ],
};

const categories: CommodityCategory[] = ['Energy', 'Precious Metals', 'Industrial Metals', 'Agriculture'];

// --- Component ---------------------------------------------------------------

export default function CommodityDashboard() {
  const [activeCategory, setActiveCategory] = useState<CommodityCategory>('Energy');

  const filteredCommodities = commodities.filter((c) => c.category === activeCategory);
  const exposedCompanies = exposureMap[activeCategory];

  // Generate 6 months of price data for the first commodity in the active category
  const commodityPriceData = useMemo((): CommodityPricePoint[] => {
    const first = filteredCommodities[0];
    if (!first) return [];
    const data: CommodityPricePoint[] = [];
    let price = first.price * 0.92;
    const start = new Date('2025-09-28');
    for (let i = 0; i < 130; i++) {
      const d = new Date(start);
      d.setDate(d.getDate() + i);
      const day = d.getDay();
      if (day === 0 || day === 6) continue;
      price += (Math.random() - 0.48) * price * 0.012;
      data.push({ date: d.toISOString().slice(0, 10), price: Math.round(price * 100) / 100 });
    }
    return data;
  }, [filteredCommodities]);

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Commodity Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Commodity prices, trends, and company exposure analysis
        </p>
      </div>

      {/* Category Tabs */}
      <div style={{
        ...panelStyle,
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        marginBottom: 'var(--panel-gap)',
        padding: '4px 8px',
      }}>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 14px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: activeCategory === cat ? 600 : 400,
              background: activeCategory === cat ? 'var(--color-surface-overlay)' : 'transparent',
              color: activeCategory === cat ? 'var(--color-accent-primary)' : 'var(--color-text-secondary)',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* CommodityPriceChart for selected commodity (6 months) */}
      {filteredCommodities[0] && (
        <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
          <h2 style={sectionTitle}>{filteredCommodities[0].name} Price History (6M)</h2>
          <CommodityPriceChart
            data={commodityPriceData}
            commodity={filteredCommodities[0].name}
            unit={filteredCommodities[0].unit}
            height={260}
          />
        </div>
      )}

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Price Table */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>{activeCategory} Prices</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Name', 'Price', '1D%', '1W%', '1M%', 'YTD%', '1Y Pctile'].map((h) => (
                  <th
                    key={h}
                    style={{
                      ...labelStyle,
                      textAlign: h === 'Name' ? 'left' : 'right',
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
              {filteredCommodities.map((c) => (
                <tr key={c.code} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{c.name}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginLeft: '6px' }}>{c.code}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginLeft: '6px' }}>{c.unit}</span>
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>
                    {c.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(c.change1d) }}>
                    {c.change1d >= 0 ? '+' : ''}{c.change1d.toFixed(2)}%
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(c.change1w) }}>
                    {c.change1w >= 0 ? '+' : ''}{c.change1w.toFixed(2)}%
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(c.change1m) }}>
                    {c.change1m >= 0 ? '+' : ''}{c.change1m.toFixed(2)}%
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(c.changeYtd) }}>
                    {c.changeYtd >= 0 ? '+' : ''}{c.changeYtd.toFixed(2)}%
                  </td>
                  <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                    <span style={{
                      fontFamily: 'var(--font-data)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                      borderRadius: '2px',
                      color: percentileColor(c.percentile1y),
                      background: `color-mix(in srgb, ${percentileColor(c.percentile1y)} 15%, transparent)`,
                      fontWeight: 600,
                    }}>
                      {c.percentile1y}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Exposed Companies Panel */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Exposed Companies</h2>
          <p style={{ ...labelStyle, marginTop: '-8px', marginBottom: '12px' }}>
            Top companies with {activeCategory.toLowerCase()} exposure
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {exposedCompanies.map((co) => (
              <div key={co.ticker} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-surface-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <div>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', fontWeight: 600 }}>{co.ticker}</span>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>{co.name}</span>
                  </div>
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>
                  {co.exposure}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
