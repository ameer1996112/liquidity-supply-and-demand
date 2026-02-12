"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  ColorType,
  LineStyle,
  CrosshairMode,
} from "lightweight-charts";

export interface Trade {
  entry_time: number;
  exit_time: number;
  entry_price: number;
  exit_price: number;
  side: "long" | "short";
  pnl: number;
  size: number;
}

export interface Zone {
  top: number;
  bottom: number;
  type: "demand" | "supply";
  created_at: number;
}

export interface BacktestChartProps {
  candles: CandlestickData<Time>[];
  trades?: Trade[];
  zones?: Zone[];
  height?: number;
  onTimeChange?: (time: number) => void;
}

/**
 * TradingView-style Candlestick Chart for Backtest Visualization
 *
 * Features:
 * - Candlestick chart with volume
 * - Trade markers (entry/exit)
 * - Supply/Demand zone overlays
 * - Crosshair with time/price display
 * - Zoom and pan controls
 */
export function BacktestChart({
  candles,
  trades = [],
  zones = [],
  height = 600,
  onTimeChange,
}: BacktestChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#d1d5db",
        fontSize: 12,
        fontFamily: "Inter, sans-serif",
      },
      grid: {
        vertLines: { color: "#1f1f1f", style: LineStyle.Solid },
        horzLines: { color: "#1f1f1f", style: LineStyle.Solid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "#6b7280",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#374151",
        },
        horzLine: {
          color: "#6b7280",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#374151",
        },
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#374151",
        scaleMargins: {
          top: 0.1,
          bottom: 0.2, // Space for volume
        },
      },
      width: chartContainerRef.current.clientWidth,
      height,
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    // Volume histogram
    const volumeSeries = chart.addHistogramSeries({
      color: "#6b7280",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8, // Volume at bottom 20%
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Subscribe to crosshair move
    chart.subscribeCrosshairMove((param) => {
      if (param.time && onTimeChange) {
        onTimeChange(param.time as number);
      }
    });

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [height, onTimeChange]);

  // Update candle data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    candleSeriesRef.current.setData(candles);

    // Extract volume data
    const volumeData = candles.map((candle: any) => ({
      time: candle.time,
      value: candle.volume || 0,
      color: candle.close >= candle.open ? "#22c55e40" : "#ef444440",
    }));

    volumeSeriesRef.current.setData(volumeData);

    // Fit content to visible area
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Draw Supply/Demand zones
  useEffect(() => {
    if (!chartRef.current || zones.length === 0) return;

    zones.forEach((zone) => {
      const color = zone.type === "demand" ? "#22c55e" : "#ef4444";
      const lineSeries = chartRef.current!.addLineSeries({
        color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      // Draw zone boundaries
      lineSeries.setData([
        { time: zone.created_at as Time, value: zone.top },
        { time: (zone.created_at + 86400 * 7) as Time, value: zone.top }, // 7 days forward
      ]);

      const bottomLine = chartRef.current!.addLineSeries({
        color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      bottomLine.setData([
        { time: zone.created_at as Time, value: zone.bottom },
        { time: (zone.created_at + 86400 * 7) as Time, value: zone.bottom },
      ]);
    });
  }, [zones]);

  // Draw trade markers
  useEffect(() => {
    if (!candleSeriesRef.current || trades.length === 0) return;

    const markers = trades.flatMap((trade) => [
      // Entry marker
      {
        time: trade.entry_time as Time,
        position: (trade.side === "long" ? "belowBar" : "aboveBar") as "belowBar" | "aboveBar",
        color: trade.side === "long" ? "#22c55e" : "#ef4444",
        shape: (trade.side === "long" ? "arrowUp" : "arrowDown") as "arrowUp" | "arrowDown",
        text: `${trade.side.toUpperCase()} @ ${trade.entry_price.toFixed(5)}`,
      },
      // Exit marker
      {
        time: trade.exit_time as Time,
        position: (trade.side === "long" ? "aboveBar" : "belowBar") as "aboveBar" | "belowBar",
        color: trade.pnl >= 0 ? "#22c55e" : "#ef4444",
        shape: "circle" as const,
        text: `${trade.pnl >= 0 ? "WIN" : "LOSS"} $${trade.pnl.toFixed(2)}`,
      },
    ]);

    candleSeriesRef.current.setMarkers(markers);
  }, [trades]);

  return (
    <div className="relative w-full">
      <div ref={chartContainerRef} className="w-full rounded-lg border border-gray-800" />
    </div>
  );
}
