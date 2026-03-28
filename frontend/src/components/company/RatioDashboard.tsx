import clsx from 'clsx';
import { TimeSeriesChart } from '../charts/TimeSeriesChart';
import { CHART_THEME, seriesColor } from '../charts/chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DuPontData {
  roe: number;
  profitMargin: number;
  assetTurnover: number;
  equityMultiplier: number;
}

export interface MultiplesPoint {
  period: string;
  pe: number;
  evEbitda: number;
  pbv: number;
}

export interface RatioDashboardProps {
  dupont: DuPontData;
  multiplesHistory: MultiplesPoint[];
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  DuPont Tree Node                                                   */
/* ------------------------------------------------------------------ */

function DuPontNode({ label, value }: { label: string; value: number }) {
  return (
    <div
      className="flex flex-col items-center gap-0.5"
      style={{
        background: 'var(--color-surface-raised)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--radius-md)',
        padding: '8px 12px',
        minWidth: 90,
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 'var(--text-lg)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value.toFixed(2)}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  DuPont Connector SVG                                               */
/* ------------------------------------------------------------------ */

function DuPontConnectors() {
  return (
    <svg
      width="100%"
      height="24"
      viewBox="0 0 400 24"
      preserveAspectRatio="none"
      style={{ display: 'block', overflow: 'visible' }}
    >
      {/* Center top point */}
      <line x1="200" y1="0" x2="200" y2="8" stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth="1" />
      {/* Horizontal span */}
      <line x1="66" y1="8" x2="333" y2="8" stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth="1" />
      {/* Vertical drops to children */}
      <line x1="66" y1="8" x2="66" y2="24" stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth="1" />
      <line x1="200" y1="8" x2="200" y2="24" stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth="1" />
      <line x1="333" y1="8" x2="333" y2="24" stroke={CHART_THEME.colors.surfaceBorderStrong} strokeWidth="1" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RatioDashboard({
  dupont,
  multiplesHistory,
  className,
}: RatioDashboardProps) {
  /* Transform multiples for TimeSeriesChart */
  const chartData = multiplesHistory.map((p) => ({
    date: p.period,
    value: p.pe,
    pe: p.pe,
    evEbitda: p.evEbitda,
    pbv: p.pbv,
  }));

  const multiplesSeries = [
    { key: 'pe', color: seriesColor(0), name: 'P/E' },
    { key: 'evEbitda', color: seriesColor(1), name: 'EV/EBITDA' },
    { key: 'pbv', color: seriesColor(2), name: 'P/BV' },
  ];

  return (
    <div className={clsx('flex flex-col gap-4', className)}>
      {/* DuPont Decomposition Tree */}
      <div className="terminal-panel">
        <h3 className="terminal-section-title">DuPont Decomposition</h3>

        <div className="flex flex-col items-center gap-0">
          {/* ROE (root node) */}
          <DuPontNode label="ROE" value={dupont.roe} />

          {/* Connector lines */}
          <div style={{ width: '100%', maxWidth: 400 }}>
            <DuPontConnectors />
          </div>

          {/* Component factors row */}
          <div className="flex items-start justify-between gap-4 w-full" style={{ maxWidth: 400 }}>
            <DuPontNode label="Profit Margin" value={dupont.profitMargin} />
            <div className="flex flex-col items-center gap-0.5 pt-1">
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                x
              </span>
            </div>
            <DuPontNode label="Asset Turnover" value={dupont.assetTurnover} />
            <div className="flex flex-col items-center gap-0.5 pt-1">
              <span
                style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-text-tertiary)',
                }}
              >
                x
              </span>
            </div>
            <DuPontNode label="Equity Mult." value={dupont.equityMultiplier} />
          </div>
        </div>
      </div>

      {/* Multiples History Chart */}
      <div className="terminal-panel">
        <h3 className="terminal-section-title">Valuation Multiples History</h3>
        <TimeSeriesChart
          data={chartData}
          series={multiplesSeries}
          height={260}
          showLegend
          yAxisFormat={(v) => `${v.toFixed(1)}x`}
        />
      </div>
    </div>
  );
}
