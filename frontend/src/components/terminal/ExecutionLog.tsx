'use client';

import { useState, useEffect, useRef } from 'react';

interface LogEntry {
  id: number;
  ts: string;
  level: 'INFO' | 'EXEC' | 'WARN' | 'ERR' | 'SYS';
  msg: string;
}

const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  INFO: '#2a2a2a',
  EXEC: '#1E90FF',
  WARN: '#FFB300',
  ERR: '#FF3B47',
  SYS: '#333',
};

const LEVEL_LABEL_COLOR: Record<LogEntry['level'], string> = {
  INFO: '#333',
  EXEC: '#1E90FF',
  WARN: '#FFB300',
  ERR: '#FF3B47',
  SYS: '#2a2a2a',
};

const SEED_LOGS: Omit<LogEntry, 'id'>[] = [
  { ts: '09:14:02', level: 'SYS', msg: 'System boot — all modules nominal' },
  { ts: '09:14:03', level: 'SYS', msg: 'WebSocket connected → broker feed' },
  { ts: '09:14:05', level: 'INFO', msg: 'Strategy LSND_v3 loaded · XAUUSD M5' },
  { ts: '09:14:07', level: 'INFO', msg: 'Strategy LSND_v3 loaded · GBPJPY M5' },
  {
    ts: '09:15:00',
    level: 'INFO',
    msg: 'Candle close XAUUSD M5 · O:2338.4 C:2339.1',
  },
  {
    ts: '09:15:01',
    level: 'EXEC',
    msg: 'SIGNAL BUY XAUUSD · conf=0.87 · lot=0.50',
  },
  {
    ts: '09:15:02',
    level: 'EXEC',
    msg: 'ORDER SENT #P001 · XAUUSD BUY 0.50 @ 2338.40',
  },
  {
    ts: '09:15:02',
    level: 'EXEC',
    msg: 'ORDER FILLED #P001 · slippage=0.1pip',
  },
  {
    ts: '09:16:00',
    level: 'INFO',
    msg: 'Candle close GBPJPY M5 · O:196.82 C:196.71',
  },
  {
    ts: '09:16:01',
    level: 'EXEC',
    msg: 'SIGNAL SELL GBPJPY · conf=0.81 · lot=0.30',
  },
  {
    ts: '09:16:02',
    level: 'EXEC',
    msg: 'ORDER SENT #P002 · GBPJPY SELL 0.30 @ 196.82',
  },
  {
    ts: '09:16:02',
    level: 'EXEC',
    msg: 'ORDER FILLED #P002 · slippage=0.2pip',
  },
  { ts: '09:20:00', level: 'INFO', msg: 'Risk check passed · drawdown=1.2%' },
  {
    ts: '09:22:15',
    level: 'WARN',
    msg: 'Spread widening EURUSD · 2.1pip > threshold',
  },
  {
    ts: '09:25:00',
    level: 'INFO',
    msg: 'Candle close NAS100 M5 · O:18150 C:18162',
  },
  {
    ts: '09:25:01',
    level: 'EXEC',
    msg: 'SIGNAL BUY NAS100 · conf=0.92 · lot=0.10',
  },
  {
    ts: '09:25:02',
    level: 'EXEC',
    msg: 'ORDER SENT #P003 · NAS100 BUY 0.10 @ 18150.0',
  },
  {
    ts: '09:25:02',
    level: 'EXEC',
    msg: 'ORDER FILLED #P003 · slippage=0.5pip',
  },
  { ts: '09:30:00', level: 'INFO', msg: 'Heartbeat OK · latency=4ms' },
  {
    ts: '09:31:44',
    level: 'EXEC',
    msg: 'SL MOVED #P001 · 2330.0 → 2334.0 (breakeven+)',
  },
  {
    ts: '09:35:00',
    level: 'INFO',
    msg: 'Candle close EURUSD M5 · O:1.0882 C:1.0871',
  },
  {
    ts: '09:35:01',
    level: 'EXEC',
    msg: 'SIGNAL BUY EURUSD · conf=0.74 · lot=1.00',
  },
  {
    ts: '09:35:02',
    level: 'EXEC',
    msg: 'ORDER SENT #P004 · EURUSD BUY 1.00 @ 1.08820',
  },
  {
    ts: '09:35:02',
    level: 'EXEC',
    msg: 'ORDER FILLED #P004 · slippage=0.1pip',
  },
  { ts: '09:40:00', level: 'INFO', msg: 'Heartbeat OK · latency=3ms' },
  {
    ts: '09:42:10',
    level: 'WARN',
    msg: 'P004 EURUSD drawdown -$110 · monitoring',
  },
];

const LIVE_TEMPLATES: Omit<LogEntry, 'id' | 'ts'>[] = [
  { level: 'INFO', msg: 'Heartbeat OK · latency=3ms' },
  { level: 'INFO', msg: 'Candle close XAUUSD M5 · price update' },
  { level: 'EXEC', msg: 'TP PARTIAL #P003 · NAS100 +$272 locked' },
  { level: 'INFO', msg: 'Risk check passed · drawdown=1.4%' },
  { level: 'EXEC', msg: 'SL TRAIL #P002 · GBPJPY adjusted' },
  { level: 'WARN', msg: 'High volatility detected · XAUUSD' },
  { level: 'INFO', msg: 'Candle close GBPJPY M5 · price update' },
  { level: 'EXEC', msg: 'SIGNAL SCAN complete · 0 new setups' },
  { level: 'INFO', msg: 'Portfolio snapshot saved' },
  { level: 'EXEC', msg: 'ORDER MODIFIED #P005 · TP adjusted' },
];

function nowTs() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes()
  ).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

let _id = SEED_LOGS.length + 1;

export function ExecutionLog() {
  const [logs, setLogs] = useState<LogEntry[]>(() =>
    SEED_LOGS.map((l, i) => ({ ...l, id: i + 1 }))
  );
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Append live log entries
  useEffect(() => {
    const id = setInterval(() => {
      const tmpl =
        LIVE_TEMPLATES[Math.floor(Math.random() * LIVE_TEMPLATES.length)];
      const entry: LogEntry = { ...tmpl, id: _id++, ts: nowTs() };
      setLogs((prev) => [...prev.slice(-200), entry]);
    }, 2200);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  return (
    <div style={styles.wrapper}>
      <div
        style={styles.logBody}
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom =
            el.scrollHeight - el.scrollTop - el.clientHeight < 40;
          setAutoScroll(atBottom);
        }}
      >
        {logs.map((entry) => (
          <div key={entry.id} style={styles.logRow}>
            <span style={styles.logTs}>{entry.ts}</span>
            <span
              style={{
                ...styles.logLevel,
                color: LEVEL_LABEL_COLOR[entry.level],
              }}
            >
              {entry.level.padEnd(4)}
            </span>
            <span
              style={{
                ...styles.logMsg,
                color:
                  LEVEL_COLOR[entry.level] === '#2a2a2a'
                    ? '#3a3a3a'
                    : LEVEL_COLOR[entry.level],
              }}
            >
              {entry.msg}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Bottom bar */}
      <div style={styles.logFooter}>
        <span style={styles.logFooterText}>{logs.length} ENTRIES</span>
        <span style={styles.logFooterSep} />
        <button
          style={{
            ...styles.logFooterBtn,
            color: autoScroll ? '#1E90FF' : '#333',
          }}
          onClick={() => setAutoScroll((v) => !v)}
        >
          {autoScroll ? '▼ AUTO' : '⏸ PAUSED'}
        </button>
        <span style={styles.logFooterSep} />
        <button style={styles.logFooterBtn} onClick={() => setLogs([])}>
          CLR
        </button>
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
  logBody: {
    flex: 1,
    overflowY: 'auto',
    overflowX: 'hidden',
    padding: '4px 0',
    scrollbarWidth: 'thin',
    scrollbarColor: '#1a1a1a transparent',
  },
  logRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 6,
    padding: '1px 10px',
    minHeight: 18,
  },
  logTs: {
    fontFamily: 'monospace',
    fontSize: 9,
    color: '#222',
    flexShrink: 0,
    letterSpacing: '0.04em',
  },
  logLevel: {
    fontFamily: 'monospace',
    fontSize: 9,
    fontWeight: 700,
    flexShrink: 0,
    letterSpacing: '0.06em',
    width: 32,
  },
  logMsg: {
    fontFamily: 'monospace',
    fontSize: 9,
    lineHeight: 1.5,
    wordBreak: 'break-all',
  },
  logFooter: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    height: 24,
    minHeight: 24,
    borderTop: BORDER,
    background: '#080808',
    paddingLeft: 10,
    flexShrink: 0,
  },
  logFooterText: {
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#222',
    letterSpacing: '0.08em',
  },
  logFooterSep: {
    width: 1,
    height: 10,
    background: '#1a1a1a',
    display: 'inline-block',
  },
  logFooterBtn: {
    background: 'transparent',
    border: 'none',
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#333',
    cursor: 'pointer',
    letterSpacing: '0.08em',
    padding: 0,
  },
};
