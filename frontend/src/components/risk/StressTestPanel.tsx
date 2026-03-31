import { DataTable } from '@/components/ui/DataTable';
import type { Column } from '@/components/ui/DataTable';

export interface StressScenario {
  scenario: string;
  portfolioPnL: number;
  benchmarkPnL: number;
  relative: number;
  [key: string]: unknown;
}

export interface StressTestPanelProps {
  scenarios: StressScenario[];
}

function signalColor(v: number): string {
  if (v > 0) return 'var(--color-signal-positive)';
  if (v < 0) return 'var(--color-signal-negative)';
  return 'var(--color-text-primary)';
}

function pctCell(v: unknown) {
  const val = v as number;
  const sign = val >= 0 ? '+' : '';
  return (
    <span
      style={{
        fontFamily: 'var(--font-data)',
        fontVariantNumeric: 'tabular-nums',
        color: signalColor(val),
        fontSize: 'var(--text-xs)',
      }}
    >
      {sign}{val.toFixed(2)}%
    </span>
  );
}

const columns: Column<StressScenario>[] = [
  {
    key: 'scenario',
    name: 'Scenario',
    width: '180px',
    format: (v) => (
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)' }}>
        {v as string}
      </span>
    ),
  },
  { key: 'portfolioPnL', name: 'Portfolio P&L', align: 'right', width: '110px', format: pctCell },
  { key: 'benchmarkPnL', name: 'Benchmark P&L', align: 'right', width: '110px', format: pctCell },
  { key: 'relative', name: 'Relative', align: 'right', width: '90px', format: pctCell },
];

export function StressTestPanel({ scenarios }: StressTestPanelProps) {
  const worstScenario = scenarios.reduce(
    (worst, s) => (s.portfolioPnL < worst.portfolioPnL ? s : worst),
    scenarios[0] ?? { scenario: '', portfolioPnL: 0, benchmarkPnL: 0, relative: 0 },
  );

  return (
    <div className="animate-in">
      <DataTable<StressScenario>
        columns={columns}
        data={scenarios}
        compact
        sortable
        rowKey={(row) => row.scenario}
        renderExpanded={undefined}
        // Highlight worst scenario via onRowClick styling is not directly supported;
        // use a custom wrapper instead
      />
      {worstScenario && (
        <div
          style={{
            marginTop: 'var(--space-2)',
            padding: '6px 10px',
            borderLeft: '3px solid var(--color-signal-warning)',
            background: 'var(--color-surface-raised)',
            borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-secondary)',
          }}
        >
          Most severe:{' '}
          <span style={{ color: 'var(--color-signal-warning)', fontWeight: 600 }}>
            {worstScenario.scenario}
          </span>{' '}
          &mdash;{' '}
          <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-signal-negative)', fontVariantNumeric: 'tabular-nums' }}>
            {worstScenario.portfolioPnL.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}

export default StressTestPanel;
