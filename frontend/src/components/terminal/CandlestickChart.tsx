'use client';

import { useEffect, useRef, useState } from 'react';

// ─── Candle data generator ────────────────────────────────────────────────────
interface Candle {
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  t: number; // unix ms
}

function generateCandles(count: number): Candle[] {
  const candles: Candle[] = [];
  let price = 2341.5;
  const now = Date.now();
  const interval = 5 * 60 * 1000; // 5 min

  for (let i = count - 1; i >= 0; i--) {
    const open = price + (Math.random() - 0.5) * 4;
    const move = (Math.random() - 0.48) * 6;
    const close = open + move;
    const high = Math.max(open, close) + Math.random() * 3;
    const low = Math.min(open, close) - Math.random() * 3;
    const vol = 200 + Math.random() * 800;
    candles.push({
      o: open,
      h: high,
      l: low,
      c: close,
      v: vol,
      t: now - i * interval,
    });
    price = close;
  }
  return candles;
}

// ─── Price scale helpers ──────────────────────────────────────────────────────
function niceRange(min: number, max: number, steps = 6) {
  const range = max - min;
  const step = range / steps;
  const levels: number[] = [];
  for (let i = 0; i <= steps; i++) {
    levels.push(min + step * i);
  }
  return levels;
}

function formatTime(ts: number) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes()
  ).padStart(2, '0')}`;
}

// ─── Component ────────────────────────────────────────────────────────────────
export function CandlestickChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [candles, setCandles] = useState<Candle[]>(() => generateCandles(80));
  const [dims, setDims] = useState({ w: 800, h: 300 });

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDims({ w: Math.max(width, 200), h: Math.max(height, 100) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Simulate live tick every 3s
  useEffect(() => {
    const id = setInterval(() => {
      setCandles((prev) => {
        const last = prev[prev.length - 1];
        const move = (Math.random() - 0.48) * 2;
        const newClose = last.c + move;
        const updated = {
          ...last,
          c: newClose,
          h: Math.max(last.h, newClose),
          l: Math.min(last.l, newClose),
        };
        // Every ~30s push a new candle
        if (Date.now() - last.t > 30_000) {
          const next: Candle = {
            o: newClose,
            h: newClose + Math.random() * 2,
            l: newClose - Math.random() * 2,
            c: newClose,
            v: 200 + Math.random() * 600,
            t: Date.now(),
          };
          return [...prev.slice(1), next];
        }
        return [...prev.slice(0, -1), updated];
      });
    }, 3000);
    return () => clearInterval(id);
  }, []);

  // Layout constants
  const PAD_LEFT = 8;
  const PAD_RIGHT = 56; // price axis
  const PAD_TOP = 12;
  const PAD_BOTTOM = 28; // time axis
  const VOL_H = Math.floor(dims.h * 0.18);
  const CHART_H = dims.h - PAD_TOP - PAD_BOTTOM - VOL_H - 4;
  const CHART_W = dims.w - PAD_LEFT - PAD_RIGHT;

  // Visible candles
  const visible = candles.slice(-Math.floor(CHART_W / 10));
  const prices = visible.flatMap((c) => [c.h, c.l]);
  const minP = Math.min(...prices) - 1;
  const maxP = Math.max(...prices) + 1;
  const priceRange = maxP - minP || 1;

  const maxVol = Math.max(...visible.map((c) => c.v));

  const candleW = Math.max(3, Math.floor(CHART_W / visible.length) - 1);
  const gap = Math.floor(CHART_W / visible.length);

  const toY = (p: number) => PAD_TOP + ((maxP - p) / priceRange) * CHART_H;
  const toVolY = (v: number) =>
    PAD_TOP + CHART_H + 4 + VOL_H - (v / maxVol) * VOL_H;

  const priceLevels = niceRange(minP, maxP, 5);

  // EMA-20 approximation
  const ema20: number[] = [];
  const k = 2 / 21;
  let emaVal = visible[0]?.c ?? 0;
  for (const c of visible) {
    emaVal = c.c * k + emaVal * (1 - k);
    ema20.push(emaVal);
  }
  const emaPath = ema20
    .map((v, i) => {
      const x = PAD_LEFT + i * gap + gap / 2;
      const y = toY(v);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // Current price line
  const lastClose = visible[visible.length - 1]?.c ?? 0;
  const lastY = toY(lastClose);
  const lastUp =
    (visible[visible.length - 1]?.c ?? 0) >=
    (visible[visible.length - 1]?.o ?? 0);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        background: '#0A0A0A',
        overflow: 'hidden',
      }}
    >
      <svg
        width={dims.w}
        height={dims.h}
        style={{ display: 'block', position: 'absolute', top: 0, left: 0 }}
      >
        {/* ── Grid lines ─────────────────────────────────────────────── */}
        {priceLevels.map((p, i) => {
          const y = toY(p);
          return (
            <g key={i}>
              <line
                x1={PAD_LEFT}
                y1={y}
                x2={dims.w - PAD_RIGHT}
                y2={y}
                stroke='#141414'
                strokeWidth='1'
              />
              <text
                x={dims.w - PAD_RIGHT + 4}
                y={y + 3.5}
                fill='#3a3a3a'
                fontSize='9'
                fontFamily='monospace'
              >
                {p.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* ── Volume bars ────────────────────────────────────────────── */}
        {visible.map((c, i) => {
          const x = PAD_LEFT + i * gap;
          const barH = (c.v / maxVol) * VOL_H || 1;
          const y = PAD_TOP + CHART_H + 4 + VOL_H - barH;
          const up = c.c >= c.o;
          return (
            <rect
              key={`v${i}`}
              x={x + 1}
              y={y}
              width={Math.max(candleW - 1, 1)}
              height={barH}
              fill={up ? 'rgba(0,200,83,0.18)' : 'rgba(255,59,71,0.18)'}
            />
          );
        })}

        {/* ── EMA line ───────────────────────────────────────────────── */}
        <path
          d={emaPath}
          fill='none'
          stroke='rgba(30,144,255,0.55)'
          strokeWidth='1'
        />

        {/* ── Candles ────────────────────────────────────────────────── */}
        {visible.map((c, i) => {
          const x = PAD_LEFT + i * gap;
          const cx = x + gap / 2;
          const up = c.c >= c.o;
          const color = up ? '#00C853' : '#FF3B47';
          const bodyTop = toY(Math.max(c.o, c.c));
          const bodyBot = toY(Math.min(c.o, c.c));
          const bodyH = Math.max(bodyBot - bodyTop, 1);
          const wickTop = toY(c.h);
          const wickBot = toY(c.l);

          return (
            <g key={`c${i}`}>
              {/* Wick */}
              <line
                x1={cx}
                y1={wickTop}
                x2={cx}
                y2={wickBot}
                stroke={color}
                strokeWidth='1'
              />
              {/* Body */}
              <rect
                x={x + 1}
                y={bodyTop}
                width={Math.max(candleW - 1, 1)}
                height={bodyH}
                fill={up ? '#00C853' : '#FF3B47'}
                fillOpacity={up ? 0.85 : 0.9}
              />
            </g>
          );
        })}

        {/* ── Current price line ─────────────────────────────────────── */}
        <line
          x1={PAD_LEFT}
          y1={lastY}
          x2={dims.w - PAD_RIGHT}
          y2={lastY}
          stroke={lastUp ? '#00C853' : '#FF3B47'}
          strokeWidth='1'
          strokeDasharray='3,3'
          opacity='0.7'
        />
        {/* Price label */}
        <rect
          x={dims.w - PAD_RIGHT}
          y={lastY - 8}
          width={PAD_RIGHT - 2}
          height={16}
          fill={lastUp ? '#00C853' : '#FF3B47'}
        />
        <text
          x={dims.w - PAD_RIGHT + 3}
          y={lastY + 4}
          fill='#000'
          fontSize='9'
          fontFamily='monospace'
          fontWeight='700'
        >
          {lastClose.toFixed(2)}
        </text>

        {/* ── Time axis ──────────────────────────────────────────────── */}
        {visible
          .filter((_, i) => i % Math.ceil(visible.length / 8) === 0)
          .map((c, i) => {
            const idx = visible.indexOf(c);
            const x = PAD_LEFT + idx * gap + gap / 2;
            return (
              <text
                key={`t${i}`}
                x={x}
                y={dims.h - 6}
                fill='#2a2a2a'
                fontSize='8'
                fontFamily='monospace'
                textAnchor='middle'
              >
                {formatTime(c.t)}
              </text>
            );
          })}

        {/* ── Crosshair overlay (static decorative) ──────────────────── */}
        <line
          x1={dims.w - PAD_RIGHT - 80}
          y1={PAD_TOP}
          x2={dims.w - PAD_RIGHT - 80}
          y2={PAD_TOP + CHART_H}
          stroke='#1E90FF'
          strokeWidth='1'
          opacity='0.15'
        />
      </svg>

      {/* ── OHLC readout ─────────────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: 6,
          left: PAD_LEFT + 4,
          display: 'flex',
          gap: 14,
          fontFamily: 'monospace',
          fontSize: 10,
          pointerEvents: 'none',
        }}
      >
        {[
          { label: 'O', val: visible[visible.length - 1]?.o.toFixed(2) },
          { label: 'H', val: visible[visible.length - 1]?.h.toFixed(2) },
          { label: 'L', val: visible[visible.length - 1]?.l.toFixed(2) },
          { label: 'C', val: visible[visible.length - 1]?.c.toFixed(2) },
        ].map(({ label, val }) => (
          <span key={label} style={{ color: '#333' }}>
            {label} <span style={{ color: '#888' }}>{val}</span>
          </span>
        ))}
        <span style={{ color: '#1E90FF', opacity: 0.6 }}>EMA(20)</span>
      </div>
    </div>
  );
}
