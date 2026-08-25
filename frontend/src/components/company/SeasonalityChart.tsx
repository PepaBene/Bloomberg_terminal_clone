import { useMemo } from 'react';
import { HeatmapChart } from '@/components/charts';
import type { HeatmapDataPoint } from '@/components/charts';
import { useSecurityPrices } from '@/hooks';
import { EmptyState } from '@/components/feedback';

/* ------------------------------------------------------------------ */
/*  Seasonality — monthly returns by year, computed client-side from   */
/*  the same real EOD price history the price chart uses (there's no   */
/*  dedicated seasonality endpoint on the backend; this needs no new   */
/*  one — it's the classic Bloomberg SEAG screen: a calendar of         */
/*  month-over-month returns, one row per year, colored by magnitude). */
/* ------------------------------------------------------------------ */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

interface EODPriceRow {
  price_date: string;
  close: number | null;
}
interface PaginatedPrices {
  data: EODPriceRow[];
}

export interface SeasonalityChartProps {
  securityId: string | undefined;
  height?: number;
}

export function SeasonalityChart({ securityId, height }: SeasonalityChartProps) {
  const { data: pricesRaw, isLoading } = useSecurityPrices(
    securityId ?? '',
    { page_size: 1000 },
    { enabled: !!securityId },
  );

  const { rows, cols, data, years } = useMemo(() => {
    const raw = (pricesRaw as PaginatedPrices | undefined)?.data;
    const priced = Array.isArray(raw)
      ? raw.filter((r): r is EODPriceRow & { close: number } => r.close != null).slice().sort((a, b) => a.price_date.localeCompare(b.price_date))
      : [];

    // Last trading day's close for each (year, month) — a real month-end mark, not an average.
    const monthEnd = new Map<string, number>(); // key "YYYY-MM" -> close
    for (const r of priced) {
      const key = r.price_date.slice(0, 7);
      monthEnd.set(key, r.close); // later rows overwrite earlier ones within the same month
    }

    const keys = [...monthEnd.keys()].sort();
    const points: HeatmapDataPoint[] = [];
    const yearSet = new Set<string>();

    for (let i = 1; i < keys.length; i++) {
      const key = keys[i]!;
      const prevKey = keys[i - 1]!;
      // Only compute a return when the previous entry is truly the prior
      // calendar month (skip gaps rather than diffing across a hole in history).
      const [y, m] = key.split('-');
      const [py, pm] = prevKey.split('-');
      const expectedPrevMonth = m === '01' ? '12' : String(Number(m) - 1).padStart(2, '0');
      const expectedPrevYear = m === '01' ? String(Number(y) - 1) : y;
      if (pm !== expectedPrevMonth || py !== expectedPrevYear) continue;

      const cur = monthEnd.get(key)!;
      const prev = monthEnd.get(prevKey)!;
      if (prev === 0) continue;
      const ret = ((cur - prev) / prev) * 100;
      const monthLabel = MONTHS[Number(m) - 1]!;
      points.push({ row: y!, col: monthLabel, value: ret });
      yearSet.add(y!);
    }

    const sortedYears = [...yearSet].sort().reverse();
    return { rows: sortedYears, cols: MONTHS, data: points, years: sortedYears.length };
  }, [pricesRaw]);

  if (!securityId) {
    return <EmptyState icon="📅" title="No security selected" description="Search for a company to load its seasonality pattern." />;
  }
  if (isLoading) {
    return <EmptyState icon="⏳" title="Loading price history…" />;
  }
  if (years < 2) {
    return (
      <EmptyState
        icon="📅"
        title="Not enough history for seasonality"
        description="At least two years of price history are needed to compare month-over-month returns across years."
      />
    );
  }

  return (
    <HeatmapChart
      data={data}
      rows={rows}
      cols={cols}
      height={height}
      colorScale="diverging"
      valueFormat={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
    />
  );
}

export default SeasonalityChart;
