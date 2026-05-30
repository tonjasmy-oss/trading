import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
} from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import type { OHLCV } from '../types';

interface Props {
  ohlcv: OHLCV[];
  buyMarkers?: { t: number; v: number }[];
  sellMarkers?: { t: number; v: number }[];
  equityCurve?: { t: number; v: number }[];
  height?: number;
}

export default function KLineChart({
  ohlcv,
  buyMarkers,
  sellMarkers,
  equityCurve,
  height = 420,
}: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const equityRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartRef.current || !ohlcv.length) return;

    chartInstance.current?.remove();
    chartInstance.current = null;

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a2e' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#2d2d44' },
        horzLines: { color: '#2d2d44' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { borderColor: '#2d2d44' },
      rightPriceScale: { borderColor: '#2d2d44' },
    });

    chartInstance.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00c853',
      downColor: '#ff1744',
      borderUpColor: '#00c853',
      borderDownColor: '#ff1744',
      wickUpColor: '#00c853',
      wickDownColor: '#ff1744',
    });

    const candleData = ohlcv.map(d => ({
      time: d.t as import('lightweight-charts').UTCTimestamp,
      open: d.o,
      high: d.h,
      low: d.l,
      close: d.c,
    }));
    candleSeries.setData(candleData);

    if (buyMarkers?.length) {
      const buySeries = chart.addSeries(LineSeries, {
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        color: '#00e676',
      });
      buySeries.setData(
        buyMarkers.map(m => ({
          time: m.t as import('lightweight-charts').UTCTimestamp,
          value: m.v,
        })),
      );
    }

    if (sellMarkers?.length) {
      const sellSeries = chart.addSeries(LineSeries, {
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        color: '#ff5252',
      });
      sellSeries.setData(
        sellMarkers.map(m => ({
          time: m.t as import('lightweight-charts').UTCTimestamp,
          value: m.v,
        })),
      );
    }

    chart.timeScale().fitContent();
    chart.timeScale().scrollToRealTime();

    const handleResize = () => {
      if (chartRef.current && chartInstance.current) {
        chartInstance.current.applyOptions({ width: chartRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartInstance.current = null;
    };
  }, [ohlcv, buyMarkers, sellMarkers, height]);

  // Equity curve panel
  useEffect(() => {
    if (!equityRef.current || !equityCurve?.length) return;

    const chart = createChart(equityRef.current, {
      width: equityRef.current.clientWidth,
      height: 160,
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a2e' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#2d2d44' },
        horzLines: { color: '#2d2d44' },
      },
      timeScale: { borderColor: '#2d2d44' },
      rightPriceScale: { borderColor: '#2d2d44' },
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: '#00bcd4',
      topColor: 'rgba(0,188,212,0.3)',
      bottomColor: 'rgba(0,188,212,0.0)',
      lineWidth: 2,
    });
    areaSeries.setData(
      equityCurve.map(d => ({
        time: d.t as import('lightweight-charts').UTCTimestamp,
        value: d.v,
      })),
    );
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [equityCurve]);

  return (
    <div>
      <div ref={chartRef} className="w-full rounded" style={{ height }} />
      {equityCurve && equityCurve.length > 0 && (
        <div ref={equityRef} className="w-full rounded mt-2" />
      )}
    </div>
  );
}