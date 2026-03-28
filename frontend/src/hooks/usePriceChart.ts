import { useEffect, useRef, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  CrosshairMode,
} from 'lightweight-charts';
import type {
  IChartApi,
  ISeriesApi,
  MouseEventParams,
  Time,
  CandlestickData,
  HistogramData,
} from 'lightweight-charts';
import { CHART_THEME } from '@/components/charts/chartTheme';

/* ── Types ────────────────────────────────────────────────── */

export interface UsePriceChartOptions {
  data: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }[];
  showVolume?: boolean;
  onCrosshairMove?: (point: unknown) => void;
}

export interface UsePriceChartReturn {
  chartRef: React.RefObject<HTMLDivElement | null>;
  chart: IChartApi | null;
  fitContent: () => void;
  setVisibleRange: (from: string, to: string) => void;
}

/* ── Hook ─────────────────────────────────────────────────── */

export function usePriceChart(options: UsePriceChartOptions): UsePriceChartReturn {
  const { data, showVolume = true, onCrosshairMove } = options;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  /* Stable callback ref for crosshair handler */
  const crosshairCb = useCallback(
    (param: MouseEventParams<Time>) => {
      onCrosshairMove?.(param);
    },
    [onCrosshairMove],
  );

  /* --- Chart creation on mount --------------------------------- */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight || 400,
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
          style: 2,
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

    chartApiRef.current = chart;

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
    if (showVolume) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
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

    /* Resize observer for responsive sizing */
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        chart.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    ro.observe(el);

    /* Cleanup on unmount */
    return () => {
      ro.disconnect();
      chart.unsubscribeCrosshairMove(crosshairCb);
      chart.remove();
      chartApiRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
    // Re-create only when showVolume changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showVolume]);

  /* --- Data updates ---------------------------------------------- */
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
            ? `${CHART_THEME.colors.positive}80`
            : `${CHART_THEME.colors.negative}80`,
      }));
      volumeSeriesRef.current.setData(volData);
    }

    chartApiRef.current?.timeScale().fitContent();
  }, [data]);

  /* --- External control methods --------------------------------- */
  const fitContent = useCallback(() => {
    chartApiRef.current?.timeScale().fitContent();
  }, []);

  const setVisibleRange = useCallback((from: string, to: string) => {
    chartApiRef.current?.timeScale().setVisibleRange({
      from: from as Time,
      to: to as Time,
    });
  }, []);

  return {
    chartRef: containerRef,
    chart: chartApiRef.current,
    fitContent,
    setVisibleRange,
  };
}
