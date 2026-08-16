import { useMemo } from 'react';
import { WaterfallChart } from '../charts/WaterfallChart';
import type { WaterfallBar } from '../charts/WaterfallChart';

export interface AttributionSegment {
  label: string;
  contribution: number;
  type: 'allocation' | 'selection' | 'interaction' | 'total';
}

export interface AttributionWaterfallProps {
  segments: AttributionSegment[];
  height?: number;
}

export function AttributionWaterfall({ segments, height = 260 }: AttributionWaterfallProps) {
  // The 'total' segment's own `contribution` is the sum the preceding
  // allocation/selection/interaction deltas should already reach — passed
  // as an `end` bar with value 0 so WaterfallChart displays the running
  // cursor (i.e. that real sum) rather than double-adding it.
  const data: WaterfallBar[] = useMemo(
    () =>
      segments.map((s) => ({
        label: s.label,
        value: s.type === 'total' ? 0 : s.contribution,
        type: s.type === 'total' ? 'end' : 'delta',
      })),
    [segments],
  );

  return <WaterfallChart data={data} height={height} formatValue={(v) => `${v.toFixed(2)}%`} />;
}

export default AttributionWaterfall;
