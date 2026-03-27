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
import { CHART_THEME } from './chartTheme';

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

export interface CandlestickChartProps {
  data: CandlestickDataPoint[];
  height?: number;
  showVolume?: boolean;
  onCrosshairMove?: (point: unknown) => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CandlestickChart({
  data,
  height = 400,
  showVolume = true,
  onCrosshairMove,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

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

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height, position: 'relative' }}
    />
  );
}
