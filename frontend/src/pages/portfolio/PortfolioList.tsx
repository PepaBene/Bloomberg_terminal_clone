// ---------------------------------------------------------------------------
// Portfolio List — Portfolio Management Overview
// ---------------------------------------------------------------------------

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

function signalColor(value: number): string {
  return value >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

// --- Mock Data ---------------------------------------------------------------

interface PortfolioRow {
  id: string;
  name: string;
  nav: number;
  dayChange: number;
  mtdReturn: number;
  ytdReturn: number;
  positions: number;
  status: 'Active' | 'Paper' | 'Archived';
}

const portfolios: PortfolioRow[] = [
  { id: 'p1', name: 'Core Growth',         nav: 2_458_320, dayChange: 0.34,  mtdReturn: 1.82,  ytdReturn: 8.42,  positions: 24, status: 'Active' },
  { id: 'p2', name: 'Value Opportunities', nav: 1_234_780, dayChange: -0.18, mtdReturn: -0.72, ytdReturn: 3.15,  positions: 18, status: 'Active' },
  { id: 'p3', name: 'Tech Alpha',          nav: 876_540,   dayChange: 0.92,  mtdReturn: 3.41,  ytdReturn: 14.28, positions: 12, status: 'Active' },
  { id: 'p4', name: 'Dividend Income',     nav: 3_125_600, dayChange: 0.08,  mtdReturn: 0.62,  ytdReturn: 4.87,  positions: 32, status: 'Active' },
  { id: 'p5', name: 'Small Cap Ideas',     nav: 425_180,   dayChange: -0.45, mtdReturn: -1.24, ytdReturn: -2.38, positions: 15, status: 'Paper' },
  { id: 'p6', name: 'ESG Focus',           nav: 685_200,   dayChange: 0.22,  mtdReturn: 0.95,  ytdReturn: 6.12,  positions: 20, status: 'Active' },
  { id: 'p7', name: 'Macro Hedge',         nav: 1_892_400, dayChange: -0.62, mtdReturn: 0.14,  ytdReturn: 1.88,  positions: 8,  status: 'Active' },
];

function statusBadge(status: PortfolioRow['status']): React.CSSProperties {
  const base: React.CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    padding: '2px 6px',
    borderRadius: '2px',
    fontWeight: 500,
  };
  switch (status) {
    case 'Active':
      return { ...base, background: 'rgba(45, 184, 125, 0.15)', color: 'var(--color-signal-positive)' };
    case 'Paper':
      return { ...base, background: 'rgba(91, 127, 166, 0.15)', color: 'var(--color-signal-neutral)' };
    case 'Archived':
      return { ...base, background: 'rgba(84, 95, 107, 0.15)', color: 'var(--color-text-tertiary)' };
  }
}

// --- Component ---------------------------------------------------------------

export default function PortfolioList() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
            Portfolios
          </h1>
          <p style={{ ...labelStyle, marginTop: '4px' }}>
            {portfolios.length} portfolios &mdash; Total NAV {formatCurrency(portfolios.reduce((s, p) => s + p.nav, 0))}
          </p>
        </div>
        <button
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            padding: '6px 16px',
            background: 'var(--color-accent-primary)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Create Portfolio
        </button>
      </div>

      {/* Table */}
      <div style={panelStyle}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Name', 'NAV', 'Day Chg', 'MTD', 'YTD', 'Positions', 'Status'].map((h) => (
                <th
                  key={h}
                  style={{
                    ...labelStyle,
                    textAlign: h === 'Name' || h === 'Status' ? 'left' : 'right',
                    padding: 'var(--table-cell-py) var(--table-cell-px)',
                    borderBottom: '1px solid var(--color-surface-border)',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {portfolios.map((p) => (
              <tr
                key={p.id}
                style={{ height: 'var(--table-row-height)', cursor: 'pointer' }}
                onMouseOver={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'var(--color-surface-overlay)'; }}
                onMouseOut={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'; }}
              >
                <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500, color: 'var(--color-accent-primary)' }}>
                  {p.name}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  {formatCurrency(p.nav)}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(p.dayChange) }}>
                  {formatPct(p.dayChange)}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(p.mtdReturn) }}>
                  {formatPct(p.mtdReturn)}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', color: signalColor(p.ytdReturn) }}>
                  {formatPct(p.ytdReturn)}
                </td>
                <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  {p.positions}
                </td>
                <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                  <span style={statusBadge(p.status)}>{p.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
