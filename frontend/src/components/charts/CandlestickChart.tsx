import { useEffect, useRef, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CrosshairMode,
} from 'lightweight-charts';
import type {
  IChartApi,
  ISeriesApi,
  MouseEventParams,
  Time,
  CandlestickData,
  HistogramData,
  LineData,
} from 'lightweight-charts';
import { CHART_THEME, seriesColor } from './chartTheme';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CandlestickDataPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface OverlayReferenceLine {
  value: number;
  label?: string;
}

export interface OverlaySeriesDef {
  /** Stable id — used to add/remove/update the underlying series across renders */
  id: string;
  label: string;
  color: string;
  /** 0 = shares the price pane (moving averages, bands); 1+ = its own pane below (oscillators) */
  pane?: number;
  type?: 'line' | 'histogram';
  data: { time: string; value: number }[];
  /** Horizontal guide lines for oscillator panes (e.g. RSI 70/30, MACD zero line) */
  referenceLines?: OverlayReferenceLine[];
  lineWidth?: 1 | 2 | 3;
}

export interface CandlestickChartProps {
  data: CandlestickDataPoint[];
  height?: number;
  showVolume?: boolean;
  onCrosshairMove?: (point: unknown) => void;
  /** Technical-indicator overlays — moving averages/bands on the price pane, oscillators in their own panes */
  overlays?: OverlaySeriesDef[];
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CandlestickChart({
  data,
  height = 400,
  showVolume = true,
  onCrosshairMove,
  overlays = [],
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const overlaySeriesRef = useRef<Map<string, ISeriesApi<'Line'> | ISeriesApi<'Histogram'>>>(new Map());
  const overlayPriceLinesRef = useRef<Map<string, ReturnType<ISeriesApi<'Line'>['createPriceLine']>[]>>(new Map());

  /* Stable callback ref for crosshair handler */
  const crosshairCb = useCallback(
    (param: MouseEventParams<Time>) => {
      onCrosshairMove?.(param);
    },
    [onCrosshairMove],
  );

  /* --- Chart lifecycle -------------------------------------------- */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { color: CHART_THEME.colors.surfaceBase },
        textColor: CHART_THEME.colors.axis,
        fontFamily: CHART_THEME.fonts.data,
        fontSize: 10,
      },
      grid: {
        vertLines: { color: CHART_THEME.colors.grid },
        horzLines: { color: CHART_THEME.colors.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: CHART_THEME.colors.accent,
          width: 1,
          style: 2, // dashed
          labelBackgroundColor: CHART_THEME.colors.surfaceRaised,
        },
        horzLine: {
          color: CHART_THEME.colors.accent,
          width: 1,
          style: 2,
          labelBackgroundColor: CHART_THEME.colors.surfaceRaised,
        },
      },
      rightPriceScale: {
        borderColor: CHART_THEME.colors.surfaceBorder,
      },
      timeScale: {
        borderColor: CHART_THEME.colors.surfaceBorder,
        timeVisible: false,
      },
    });

    chartRef.current = chart;

    /* Candlestick series */
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: CHART_THEME.colors.positive,
      downColor: CHART_THEME.colors.negative,
      borderUpColor: CHART_THEME.colors.positive,
      borderDownColor: CHART_THEME.colors.negative,
      wickUpColor: CHART_THEME.colors.positive,
      wickDownColor: CHART_THEME.colors.negative,
    });

    candleSeriesRef.current = candleSeries;

    /* Volume histogram (20 % of chart height) */
    let volumeSeries: ISeriesApi<'Histogram'> | null = null;
    if (showVolume) {
      volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });

      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
        ticksVisible: false,
      });

      volumeSeriesRef.current = volumeSeries;
    }

    /* Crosshair subscriber */
    chart.subscribeCrosshairMove(crosshairCb);

    /* Resize observer */
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    ro.observe(el);

    /* Cleanup */
    return () => {
      ro.disconnect();
      chart.unsubscribeCrosshairMove(crosshairCb);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaySeriesRef.current.clear();
      overlayPriceLinesRef.current.clear();
    };
    // Intentionally only re-create the chart when container-level props change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height, showVolume]);

  /* --- Data updates ------------------------------------------------ */
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    const candleData: CandlestickData<Time>[] = data.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    candleSeriesRef.current.setData(candleData);

    if (volumeSeriesRef.current) {
      const volData: HistogramData<Time>[] = data.map((d) => ({
        time: d.time as Time,
        value: d.volume ?? 0,
        color:
          d.close >= d.open
            ? `${CHART_THEME.colors.positive}80` // 50 % opacity
            : `${CHART_THEME.colors.negative}80`,
      }));
      volumeSeriesRef.current.setData(volData);
    }

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  /* --- Indicator overlays -------------------------------------------
   * Reconciled against `overlays` by id: series no longer present are
   * removed, new ids get a fresh line/histogram series (in their own pane
   * when `pane > 0`), and every current series has its data refreshed. */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const seriesMap = overlaySeriesRef.current;
    const priceLineMap = overlayPriceLinesRef.current;
    const nextIds = new Set(overlays.map((o) => o.id));

    // Remove stale series
    for (const [id, series] of seriesMap) {
      if (!nextIds.has(id)) {
        chart.removeSeries(series);
        seriesMap.delete(id);
        priceLineMap.delete(id);
      }
    }

    for (const overlay of overlays) {
      let series = seriesMap.get(overlay.id);
      if (!series) {
        series =
          overlay.type === 'histogram'
            ? chart.addSeries(
                HistogramSeries,
                { color: overlay.color, priceLineVisible: false, lastValueVisible: false },
                overlay.pane ?? 0,
              )
            : chart.addSeries(
                LineSeries,
                {
                  color: overlay.color,
                  lineWidth: overlay.lineWidth ?? 2,
                  priceLineVisible: false,
                  lastValueVisible: false,
                  title: overlay.label,
                },
                overlay.pane ?? 0,
              );
        seriesMap.set(overlay.id, series);
      }

      const points = overlay.data.map((d) => ({ time: d.time as Time, value: d.value }));
      series.setData(points as LineData<Time>[] | HistogramData<Time>[]);

      // Reference lines (redraw each time — cheap, and values rarely change)
      const existingLines = priceLineMap.get(overlay.id) ?? [];
      for (const line of existingLines) series.removePriceLine(line);
      const newLines = (overlay.referenceLines ?? []).map((ref) =>
        series!.createPriceLine({
          price: ref.value,
          color: CHART_THEME.colors.surfaceBorderStrong,
          lineWidth: 1,
          lineStyle: 3, // dotted
          axisLabelVisible: true,
          title: ref.label ?? String(ref.value),
        }),
      );
      priceLineMap.set(overlay.id, newLines);
    }

    // Give the price pane the majority of the height; split the rest evenly
    // across any oscillator panes (RSI, MACD, ...) beneath it.
    const panes = chart.panes();
    if (panes.length > 1) {
      const total = panes.reduce((sum, p) => sum + p.getHeight(), 0) || height;
      const subHeight = Math.floor((total * 0.3) / (panes.length - 1));
      panes.forEach((p, i) => p.setHeight(i === 0 ? total - subHeight * (panes.length - 1) : subHeight));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlays]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height, position: 'relative' }}
    />
  );
}

/** Convenience: pick a stable overlay color from the shared categorical palette by index */
export { seriesColor as overlaySeriesColor };
