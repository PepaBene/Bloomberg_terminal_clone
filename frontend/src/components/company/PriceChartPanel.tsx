import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { CandlestickChart, seriesColor } from '@/components/charts';
import type { CandlestickDataPoint, OverlaySeriesDef } from '@/components/charts';
import { useSecurityPrices, useTechnicalSeries } from '@/hooks';
import { EmptyState } from '@/components/feedback';

/* ------------------------------------------------------------------ */
/*  Response shapes (real backend, see src/api/routers/securities.py   */
/*  and the new /v2/analytics/technical-series/{id} route)             */
/* ------------------------------------------------------------------ */

interface EODPriceRow {
  price_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}
interface PaginatedPrices {
  data: EODPriceRow[];
}
interface TechnicalSeriesResponse {
  dates: string[];
  series: Record<string, (number | null)[]>;
  data_quality: string;
}

/* ------------------------------------------------------------------ */
/*  Indicator toggle definitions                                       */
/* ------------------------------------------------------------------ */

type IndicatorKey = 'SMA_20' | 'SMA_50' | 'EMA_12' | 'EMA_26' | 'BB' | 'RSI_14' | 'MACD';

const TOGGLES: { key: IndicatorKey; label: string }[] = [
  { key: 'SMA_20', label: 'SMA 20' },
  { key: 'SMA_50', label: 'SMA 50' },
  { key: 'EMA_12', label: 'EMA 12' },
  { key: 'EMA_26', label: 'EMA 26' },
  { key: 'BB', label: 'Bollinger' },
  { key: 'RSI_14', label: 'RSI' },
  { key: 'MACD', label: 'MACD' },
];

const DEFAULT_ACTIVE: IndicatorKey[] = ['SMA_20', 'SMA_50'];

function seriesToPoints(dates: string[], values: (number | null)[] | undefined): { time: string; value: number }[] {
  if (!values) return [];
  const points: { time: string; value: number }[] = [];
  for (let i = 0; i < dates.length; i++) {
    const v = values[i];
    const t = dates[i];
    if (v != null && t) points.push({ time: t, value: v });
  }
  return points;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export interface PriceChartPanelProps {
  /** Entity/security id used by both /securities/{id}/prices and /analytics/technical-series/{id} */
  securityId: string | undefined;
  height?: number;
  title?: string;
}

export function PriceChartPanel({ securityId, height = 300 }: PriceChartPanelProps) {
  const [active, setActive] = useState<Set<IndicatorKey>>(new Set(DEFAULT_ACTIVE));

  const { data: pricesRaw, isLoading: loadingPrices } = useSecurityPrices(
    securityId ?? '',
    { page_size: 260 },
    { enabled: !!securityId },
  );
  const { data: seriesRaw } = useTechnicalSeries(securityId);

  const candles: CandlestickDataPoint[] = useMemo(() => {
    const rows = (pricesRaw as PaginatedPrices | undefined)?.data;
    if (!Array.isArray(rows)) return [];
    return rows
      .filter((r): r is EODPriceRow & { open: number; high: number; low: number; close: number } =>
        r.open != null && r.high != null && r.low != null && r.close != null,
      )
      .slice()
      .sort((a, b) => a.price_date.localeCompare(b.price_date))
      .map((r) => ({
        time: r.price_date,
        open: r.open,
        high: r.high,
        low: r.low,
        close: r.close,
        volume: r.volume ?? undefined,
      }));
  }, [pricesRaw]);

  const seriesResp = seriesRaw as TechnicalSeriesResponse | undefined;

  const overlays: OverlaySeriesDef[] = useMemo(() => {
    if (!seriesResp || seriesResp.data_quality !== 'COMPLETE') return [];
    const { dates, series } = seriesResp;
    const out: OverlaySeriesDef[] = [];

    if (active.has('SMA_20')) {
      out.push({ id: 'SMA_20', label: 'SMA 20', color: seriesColor(0), pane: 0, data: seriesToPoints(dates, series.SMA_20) });
    }
    if (active.has('SMA_50')) {
      out.push({ id: 'SMA_50', label: 'SMA 50', color: seriesColor(1), pane: 0, data: seriesToPoints(dates, series.SMA_50) });
    }
    if (active.has('EMA_12')) {
      out.push({ id: 'EMA_12', label: 'EMA 12', color: seriesColor(2), pane: 0, data: seriesToPoints(dates, series.EMA_12) });
    }
    if (active.has('EMA_26')) {
      out.push({ id: 'EMA_26', label: 'EMA 26', color: seriesColor(3), pane: 0, data: seriesToPoints(dates, series.EMA_26) });
    }
    if (active.has('BB')) {
      const bandColor = seriesColor(4);
      out.push(
        { id: 'BB_UPPER', label: 'BB Upper', color: bandColor, pane: 0, lineWidth: 1, data: seriesToPoints(dates, series.BB_UPPER) },
        { id: 'BB_MIDDLE', label: 'BB Middle', color: bandColor, pane: 0, lineWidth: 1, data: seriesToPoints(dates, series.BB_MIDDLE) },
        { id: 'BB_LOWER', label: 'BB Lower', color: bandColor, pane: 0, lineWidth: 1, data: seriesToPoints(dates, series.BB_LOWER) },
      );
    }
    if (active.has('RSI_14')) {
      out.push({
        id: 'RSI_14',
        label: 'RSI (14)',
        color: seriesColor(5),
        pane: 1,
        data: seriesToPoints(dates, series.RSI_14),
        referenceLines: [
          { value: 70, label: 'Overbought' },
          { value: 30, label: 'Oversold' },
        ],
      });
    }
    if (active.has('MACD')) {
      out.push(
        { id: 'MACD_HIST', label: 'MACD Hist', color: seriesColor(6), pane: 2, type: 'histogram', data: seriesToPoints(dates, series.MACD_HIST) },
        { id: 'MACD', label: 'MACD', color: seriesColor(6), pane: 2, data: seriesToPoints(dates, series.MACD), referenceLines: [{ value: 0 }] },
        { id: 'MACD_SIGNAL', label: 'Signal', color: seriesColor(7), pane: 2, data: seriesToPoints(dates, series.MACD_SIGNAL) },
      );
    }
    return out;
  }, [active, seriesResp]);

  const toggle = (key: IndicatorKey) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const chipStyle = (isActive: boolean): CSSProperties => ({
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    padding: '4px 10px',
    borderRadius: '3px',
    cursor: 'pointer',
    userSelect: 'none',
    background: isActive ? 'var(--color-accent-primary)' : 'var(--color-surface-overlay)',
    color: isActive ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
    border: '1px solid transparent',
  });

  return (
    <div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
        {TOGGLES.map((t) => (
          <span key={t.key} style={chipStyle(active.has(t.key))} onClick={() => toggle(t.key)}>
            {t.label}
          </span>
        ))}
      </div>

      {loadingPrices ? (
        <EmptyState icon="⏳" title="Loading price history…" />
      ) : candles.length === 0 ? (
        <EmptyState
          icon="📈"
          title="No price history available"
          description="No end-of-day price history has been ingested for this security yet."
        />
      ) : (
        <CandlestickChart data={candles} height={height} showVolume overlays={overlays} />
      )}
    </div>
  );
}

export default PriceChartPanel;
