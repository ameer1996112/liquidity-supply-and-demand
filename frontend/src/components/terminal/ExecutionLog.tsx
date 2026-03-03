'use client';

import { useState, useEffect, useRef } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

type Level = 'INFO' | 'EXEC' | 'WARN' | 'ERR' | 'SYS';

interface LogEntry {
  id: number;
  ts: string;
  level: Level;
  agent: string;        // raw agent name, e.g. "quant_agent"
  msg: string;
}

// ── Agent config ──────────────────────────────────────────────────────────────

const AGENT_META: Record<string, { label: string; color: string; level: Level }> = {
  supervisor:  { label: 'SUPERVISOR',  color: '#A0C4FF', level: 'INFO' },
  quant_agent: { label: 'QUANT',       color: '#00E5A0', level: 'EXEC' },
  risk_agent:  { label: 'RISK',        color: '#FFB300', level: 'WARN' },
  system:      { label: 'SYS',         color: '#555',    level: 'SYS'  },
};

const DEFAULT_AGENT = { label: 'SYS', color: '#666', level: 'INFO' as Level };

function agentMeta(name: string) {
  return AGENT_META[name] ?? DEFAULT_AGENT;
}

// ── Level badge colours ───────────────────────────────────────────────────────

const LEVEL_COLOR: Record<Level, string> = {
  INFO: '#A0C4FF',
  EXEC: '#00E5A0',
  WARN: '#FFB300',
  ERR:  '#FF4757',
  SYS:  '#555',
};

// ── WebSocket URL (env-aware) ─────────────────────────────────────────────────

function getWsUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://localhost:8000');

  // http → ws  |  https → wss
  const wsBase = raw.replace(/^http/, 'ws').replace(/\/$/, '');
  return `${wsBase}/ws/debate`;
}

// ── Seed logs (shown before WebSocket connects) ───────────────────────────────

const SEED: Omit<LogEntry, 'id'>[] = [
  { ts: '00:00:00', level: 'SYS',  agent: 'system',      msg: 'Council Room online — awaiting signals.' },
  { ts: '00:00:01', level: 'INFO', agent: 'supervisor',  msg: 'MAS v2 booted · Quant + Risk agents ready.' },
  { ts: '00:00:02', level: 'EXEC', agent: 'quant_agent', msg: 'LightGBM model loaded · features=21.' },
  { ts: '00:00:03', level: 'WARN', agent: 'risk_agent',  msg: 'Supabase connected · drawdown tracking active.' },
];

let _nextId = SEED.length + 1;

function nowTs() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ExecutionLog() {
  const [logs, setLogs] = useState<LogEntry[]>(() =>
    SEED.map((l, i) => ({ ...l, id: i + 1 }))
  );
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef     = useRef<WebSocket | null>(null);
  const retryRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  // WebSocket → Council Room debate stream
  useEffect(() => {
    const wsUrl = getWsUrl();

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setConnected(true);
          setLogs((prev) => [
            ...prev,
            {
              id:    _nextId++,
              ts:    nowTs(),
              level: 'SYS',
              agent: 'system',
              msg:   `Connected to Council Room (${wsUrl})`,
            },
          ]);
        };

        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data as string) as {
              agent?: string;
              message?: string;
              level?: string;
            };
            const agentName = (data.agent || 'system').toLowerCase();
            const meta = agentMeta(agentName);
            const levelMap: Record<string, Level> = {
              INFO: 'INFO', EXEC: 'EXEC', WARN: 'WARN', ERR: 'ERR', SYS: 'SYS',
            };
            const level: Level =
              levelMap[(data.level ?? '').toUpperCase()] ?? meta.level;

            setLogs((prev) => [
              ...prev.slice(-300),
              {
                id:    _nextId++,
                ts:    nowTs(),
                level,
                agent: agentName,
                msg:   data.message ?? '',
              },
            ]);
          } catch { /* skip non-JSON */ }
        };

        ws.onerror = () => setConnected(false);

        ws.onclose = () => {
          setConnected(false);
          retryRef.current = setTimeout(connect, 4000);
        };
      } catch {
        retryRef.current = setTimeout(connect, 4000);
      }
    };

    connect();

    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs, autoScroll]);

  return (
    <div style={S.wrapper}>

      {/* ── Status bar ── */}
      <div style={S.statusBar}>
        <span style={{ ...S.dot, background: connected ? '#00E5A0' : '#FFB300' }} />
        <span style={{ ...S.statusText, color: connected ? '#00E5A0' : '#FFB300' }}>
          {connected ? 'COUNCIL ROOM LIVE' : 'RECONNECTING…'}
        </span>
        <span style={S.statusSep} />
        <span style={S.statusText}>MAS v2 · Quant ⟶ Risk ⟶ Supervisor</span>
      </div>

      {/* ── Log body ── */}
      <div
        style={S.body}
        onScroll={(e) => {
          const el = e.currentTarget;
          setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
        }}
      >
        {logs.map((entry) => {
          const meta  = agentMeta(entry.agent);
          const lc    = LEVEL_COLOR[entry.level];
          return (
            <div key={entry.id} style={S.row}>
              {/* timestamp */}
              <span style={S.ts}>{entry.ts}</span>

              {/* level badge */}
              <span style={{ ...S.badge, color: lc, borderColor: lc + '44' }}>
                {entry.level}
              </span>

              {/* agent name */}
              {entry.agent !== 'system' && (
                <span style={{ ...S.agentTag, color: meta.color }}>
                  {meta.label}
                </span>
              )}

              {/* message */}
              <span style={{ ...S.msg, color: entry.level === 'SYS' ? '#444' : '#D0D0D0' }}>
                {entry.msg}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* ── Footer ── */}
      <div style={S.footer}>
        <span style={S.footerText}>{logs.length} ENTRIES</span>
        <span style={S.sep} />
        <button
          style={{ ...S.btn, color: autoScroll ? '#00E5A0' : '#555' }}
          onClick={() => setAutoScroll((v) => !v)}
        >
          {autoScroll ? '▼ AUTO' : '⏸ PAUSED'}
        </button>
        <span style={S.sep} />
        <button style={S.btn} onClick={() => setLogs([])}>CLR</button>
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const BORDER = '1px solid #1a1a1a';

const S: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex', flexDirection: 'column',
    height: '100%', overflow: 'hidden',
    background: '#080808',
    fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
  },

  // status bar
  statusBar: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '4px 12px', borderBottom: BORDER,
    background: '#060606', flexShrink: 0,
  },
  dot: { width: 6, height: 6, borderRadius: '50%', flexShrink: 0 },
  statusText: { fontSize: 9, letterSpacing: '0.12em', color: '#555' },
  statusSep: { width: 1, height: 10, background: '#1e1e1e', display: 'inline-block' },

  // log body
  body: {
    flex: 1, overflowY: 'auto', overflowX: 'hidden',
    padding: '6px 0',
    scrollbarWidth: 'thin', scrollbarColor: '#1a1a1a transparent',
  },

  // single row
  row: {
    display: 'flex', alignItems: 'baseline',
    gap: 7, padding: '1.5px 12px', minHeight: 20,
  },
  ts: { fontSize: 9, color: '#2e2e2e', flexShrink: 0, letterSpacing: '0.04em', minWidth: 54 },
  badge: {
    fontSize: 8, fontWeight: 700, letterSpacing: '0.1em',
    border: '1px solid', borderRadius: 2,
    padding: '0 3px', flexShrink: 0, minWidth: 32, textAlign: 'center',
  },
  agentTag: {
    fontSize: 8, fontWeight: 700, letterSpacing: '0.12em',
    flexShrink: 0, minWidth: 68,
  },
  msg: { fontSize: 10, lineHeight: 1.55, wordBreak: 'break-word' },

  // footer
  footer: {
    display: 'flex', alignItems: 'center',
    gap: 8, height: 26, minHeight: 26,
    borderTop: BORDER, background: '#060606',
    paddingLeft: 12, flexShrink: 0,
  },
  footerText: { fontSize: 8, color: '#333', letterSpacing: '0.1em' },
  sep: { width: 1, height: 10, background: '#1e1e1e', display: 'inline-block' },
  btn: {
    background: 'transparent', border: 'none', cursor: 'pointer',
    fontSize: 8, color: '#444', letterSpacing: '0.1em', padding: 0,
    fontFamily: 'inherit',
  },
};
