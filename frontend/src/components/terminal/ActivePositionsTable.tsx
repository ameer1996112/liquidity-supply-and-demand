'use client';

import { useState, useEffect } from 'react';

interface Position {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  lots: number;
  openPrice: number;
  currentPrice: number;
  sl: number;
  tp: number;
  pnl: number;
  pnlPct: number;
  duration: string;
  account: string;
}

const INITIAL_POSITIONS: Position[] = [
  {
    id: 'P001',
    symbol: 'XAUUSD',
    side: 'BUY',
    lots: 0.5,
    openPrice: 2338.4,
    currentPrice: 2341.8,
    sl: 2330.0,
    tp: 2360.0,
    pnl: 170.0,
    pnlPct: 0.15,
    duration: '1h 24m',
    account: 'FTMO-01',
  },
  {
    id: 'P002',
    symbol: 'GBPJPY',
    side: 'SELL',
    lots: 0.3,
    openPrice: 196.82,
    currentPrice: 196.34,
    sl: 197.5,
    tp: 195.0,
    pnl: 144.0,
    pnlPct: 0.24,
    duration: '42m',
    account: 'FTMO-01',
  },
  {
    id: 'P003',
    symbol: 'NAS100',
    side: 'BUY',
    lots: 0.1,
    openPrice: 18150.0,
    currentPrice: 18204.5,
    sl: 18050.0,
    tp: 18400.0,
    pnl: 545.0,
    pnlPct: 0.3,
    duration: '3h 07m',
    account: 'MFF-02',
  },
  {
    id: 'P004',
    symbol: 'EURUSD',
    side: 'BUY',
    lots: 1.0,
    openPrice: 1.0882,
    currentPrice: 1.0871,
    sl: 1.084,
    tp: 1.095,
    pnl: -110.0,
    pnlPct: -0.1,
    duration: '28m',
    account: 'MFF-02',
  },
  {
    id: 'P005',
    symbol: 'GBPUSD',
    side: 'SELL',
    lots: 0.5,
    openPrice: 1.268,
    currentPrice: 1.2654,
    sl: 1.272,
    tp: 1.258,
    pnl: 130.0,
    pnlPct: 0.2,
    duration: '55m',
    account: 'FTMO-01',
  },
  {
    id: 'P006',
    symbol: 'USDJPY',
    side: 'BUY',
    lots: 0.4,
    openPrice: 154.42,
    currentPrice: 154.82,
    sl: 153.8,
    tp: 156.0,
    pnl: 103.5,
    pnlPct: 0.26,
    duration: '2h 11m',
    account: 'MFF-02',
  },
];

const COL_HEADERS = [
  { label: '#', w: 36 },
  { label: 'SYMBOL', w: 72 },
  { label: 'SIDE', w: 44 },
  { label: 'LOTS', w: 44 },
  { label: 'OPEN', w: 72 },
  { label: 'CURRENT', w: 72 },
  { label: 'SL', w: 64 },
  { label: 'TP', w: 64 },
  { label: 'P&L', w: 80 },
  { label: 'DURATION', w: 64 },
  { label: 'ACCOUNT', w: 72 },
];

export function ActivePositionsTable() {
  const [positions, setPositions] = useState<Position[]>(INITIAL_POSITIONS);
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);

  // Simulate live P&L ticks
  useEffect(() => {
    const id = setInterval(() => {
      setPositions((prev) =>
        prev.map((p) => {
          const delta = (Math.random() - 0.48) * 8;
          const newPnl = p.pnl + delta;
          const newCurrent =
            p.side === 'BUY'
              ? p.openPrice + newPnl / (p.lots * 100)
              : p.openPrice - newPnl / (p.lots * 100);
          return {
            ...p,
            pnl: newPnl,
            currentPrice: parseFloat(
              newCurrent.toFixed(
                p.symbol === 'XAUUSD' ? 2 : p.symbol === 'NAS100' ? 1 : 5
              )
            ),
          };
        })
      );
    }, 2500);
    return () => clearInterval(id);
  }, []);

  const totalPnl = positions.reduce((s, p) => s + p.pnl, 0);

  return (
    <div style={styles.wrapper}>
      {/* Table header */}
      <div style={styles.thead}>
        {COL_HEADERS.map((col) => (
          <div
            key={col.label}
            style={{ ...styles.th, width: col.w, minWidth: col.w }}
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Table body */}
      <div style={styles.tbody}>
        {positions.map((p) => {
          const up = p.pnl >= 0;
          const isHovered = hoveredRow === p.id;
          return (
            <div
              key={p.id}
              style={{
                ...styles.tr,
                background: isHovered ? 'rgba(30,144,255,0.04)' : 'transparent',
              }}
              onMouseEnter={() => setHoveredRow(p.id)}
              onMouseLeave={() => setHoveredRow(null)}
            >
              {/* # */}
              <div
                style={{
                  ...styles.td,
                  width: 36,
                  minWidth: 36,
                  color: '#2a2a2a',
                }}
              >
                {p.id}
              </div>
              {/* Symbol */}
              <div
                style={{
                  ...styles.td,
                  width: 72,
                  minWidth: 72,
                  color: '#ccc',
                  fontWeight: 600,
                }}
              >
                {p.symbol}
              </div>
              {/* Side */}
              <div style={{ ...styles.td, width: 44, minWidth: 44 }}>
                <span
                  style={{
                    ...styles.sideBadge,
                    color: p.side === 'BUY' ? '#00C853' : '#FF3B47',
                    borderColor:
                      p.side === 'BUY'
                        ? 'rgba(0,200,83,0.25)'
                        : 'rgba(255,59,71,0.25)',
                  }}
                >
                  {p.side}
                </span>
              </div>
              {/* Lots */}
              <div
                style={{ ...styles.td, width: 44, minWidth: 44, color: '#666' }}
              >
                {p.lots.toFixed(2)}
              </div>
              {/* Open */}
              <div
                style={{ ...styles.td, width: 72, minWidth: 72, color: '#555' }}
              >
                {p.openPrice.toFixed(
                  p.symbol === 'XAUUSD' ? 2 : p.symbol === 'NAS100' ? 1 : 5
                )}
              </div>
              {/* Current */}
              <div
                style={{ ...styles.td, width: 72, minWidth: 72, color: '#aaa' }}
              >
                {p.currentPrice.toFixed(
                  p.symbol === 'XAUUSD' ? 2 : p.symbol === 'NAS100' ? 1 : 5
                )}
              </div>
              {/* SL */}
              <div
                style={{
                  ...styles.td,
                  width: 64,
                  minWidth: 64,
                  color: 'rgba(255,59,71,0.5)',
                }}
              >
                {p.sl.toFixed(
                  p.symbol === 'XAUUSD' ? 2 : p.symbol === 'NAS100' ? 1 : 5
                )}
              </div>
              {/* TP */}
              <div
                style={{
                  ...styles.td,
                  width: 64,
                  minWidth: 64,
                  color: 'rgba(0,200,83,0.5)',
                }}
              >
                {p.tp.toFixed(
                  p.symbol === 'XAUUSD' ? 2 : p.symbol === 'NAS100' ? 1 : 5
                )}
              </div>
              {/* P&L */}
              <div style={{ ...styles.td, width: 80, minWidth: 80 }}>
                <span
                  style={{ color: up ? '#00C853' : '#FF3B47', fontWeight: 600 }}
                >
                  {up ? '+' : ''}
                  {p.pnl.toFixed(2)}
                </span>
                <span
                  style={{
                    color: up ? 'rgba(0,200,83,0.45)' : 'rgba(255,59,71,0.45)',
                    fontSize: 8,
                    marginLeft: 3,
                  }}
                >
                  {up ? '+' : ''}
                  {p.pnlPct.toFixed(2)}%
                </span>
              </div>
              {/* Duration */}
              <div
                style={{ ...styles.td, width: 64, minWidth: 64, color: '#333' }}
              >
                {p.duration}
              </div>
              {/* Account */}
              <div
                style={{
                  ...styles.td,
                  width: 72,
                  minWidth: 72,
                  color: '#1E90FF',
                  opacity: 0.6,
                }}
              >
                {p.account}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer totals */}
      <div style={styles.tfoot}>
        <span style={styles.tfootLabel}>TOTAL NET P&amp;L</span>
        <span
          style={{
            ...styles.tfootVal,
            color: totalPnl >= 0 ? '#00C853' : '#FF3B47',
          }}
        >
          {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
        </span>
        <span style={styles.tfootSep} />
        <span style={styles.tfootLabel}>POSITIONS</span>
        <span style={{ ...styles.tfootVal, color: '#1E90FF' }}>
          {positions.length}
        </span>
        <span style={styles.tfootSep} />
        <span style={styles.tfootLabel}>EXPOSURE</span>
        <span style={{ ...styles.tfootVal, color: '#888' }}>
          {positions.reduce((s, p) => s + p.lots, 0).toFixed(2)} LOTS
        </span>
      </div>
    </div>
  );
}

const BORDER = '1px solid #141414';

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
    background: '#0A0A0A',
  },
  thead: {
    display: 'flex',
    alignItems: 'center',
    height: 26,
    minHeight: 26,
    borderBottom: BORDER,
    background: '#080808',
    flexShrink: 0,
    paddingLeft: 8,
    overflowX: 'hidden',
  },
  th: {
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#2a2a2a',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    flexShrink: 0,
    paddingRight: 8,
  },
  tbody: {
    flex: 1,
    overflowY: 'auto',
    overflowX: 'hidden',
    scrollbarWidth: 'thin',
    scrollbarColor: '#1a1a1a transparent',
  },
  tr: {
    display: 'flex',
    alignItems: 'center',
    height: 30,
    borderBottom: '1px solid #0f0f0f',
    paddingLeft: 8,
    cursor: 'default',
    transition: 'background 0.1s',
  },
  td: {
    fontFamily: 'monospace',
    fontSize: 10,
    flexShrink: 0,
    paddingRight: 8,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  sideBadge: {
    fontFamily: 'monospace',
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: '0.08em',
    border: '1px solid',
    padding: '1px 4px',
  },
  tfoot: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    height: 28,
    minHeight: 28,
    borderTop: BORDER,
    background: '#080808',
    paddingLeft: 12,
    flexShrink: 0,
  },
  tfootLabel: {
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#2a2a2a',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
  },
  tfootVal: {
    fontFamily: 'monospace',
    fontSize: 10,
    fontWeight: 600,
  },
  tfootSep: {
    width: 1,
    height: 12,
    background: '#1a1a1a',
    display: 'inline-block',
    marginLeft: 4,
  },
};
