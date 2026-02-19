'use client';

import { useState, useEffect, useRef } from 'react';
import { CandlestickChart } from './CandlestickChart';
import { ActivePositionsTable } from './ActivePositionsTable';
import { ExecutionLog } from './ExecutionLog';
import { WalletMargin } from './WalletMargin';

// ─── Nav icons (inline SVG to avoid any icon lib dependency) ─────────────────
function IconDashboard({ active }: { active: boolean }) {
  return (
    <svg
      width='18'
      height='18'
      viewBox='0 0 24 24'
      fill='none'
      stroke={active ? '#1E90FF' : '#555'}
      strokeWidth='1.6'
      strokeLinecap='square'
    >
      <rect x='3' y='3' width='7' height='7' />
      <rect x='14' y='3' width='7' height='7' />
      <rect x='3' y='14' width='7' height='7' />
      <rect x='14' y='14' width='7' height='7' />
    </svg>
  );
}
function IconStrategies({ active }: { active: boolean }) {
  return (
    <svg
      width='18'
      height='18'
      viewBox='0 0 24 24'
      fill='none'
      stroke={active ? '#1E90FF' : '#555'}
      strokeWidth='1.6'
      strokeLinecap='square'
    >
      <polyline points='22 12 18 12 15 21 9 3 6 12 2 12' />
    </svg>
  );
}
function IconRisk({ active }: { active: boolean }) {
  return (
    <svg
      width='18'
      height='18'
      viewBox='0 0 24 24'
      fill='none'
      stroke={active ? '#1E90FF' : '#555'}
      strokeWidth='1.6'
      strokeLinecap='square'
    >
      <path d='M12 2L2 19h20L12 2z' />
      <line x1='12' y1='9' x2='12' y2='13' />
      <line x1='12' y1='17' x2='12.01' y2='17' />
    </svg>
  );
}
function IconLogs({ active }: { active: boolean }) {
  return (
    <svg
      width='18'
      height='18'
      viewBox='0 0 24 24'
      fill='none'
      stroke={active ? '#1E90FF' : '#555'}
      strokeWidth='1.6'
      strokeLinecap='square'
    >
      <line x1='4' y1='6' x2='20' y2='6' />
      <line x1='4' y1='10' x2='20' y2='10' />
      <line x1='4' y1='14' x2='14' y2='14' />
      <line x1='4' y1='18' x2='10' y2='18' />
    </svg>
  );
}

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', Icon: IconDashboard },
  { id: 'strategies', label: 'Strategies', Icon: IconStrategies },
  { id: 'risk', label: 'Risk', Icon: IconRisk },
  { id: 'logs', label: 'Logs', Icon: IconLogs },
];

// ─── Ticker bar data ──────────────────────────────────────────────────────────
const TICKERS = [
  { sym: 'XAUUSD', price: '2 341.80', chg: '+0.42%', up: true },
  { sym: 'GBPJPY', price: '196.342', chg: '-0.18%', up: false },
  { sym: 'NAS100', price: '18 204.5', chg: '+0.91%', up: true },
  { sym: 'EURUSD', price: '1.08712', chg: '+0.07%', up: true },
  { sym: 'GBPUSD', price: '1.26540', chg: '-0.23%', up: false },
  { sym: 'USDJPY', price: '154.820', chg: '+0.31%', up: true },
  { sym: 'CHFJPY', price: '172.114', chg: '-0.09%', up: false },
  { sym: 'GBPCAD', price: '1.71830', chg: '+0.14%', up: true },
];

export function TradingTerminal() {
  const [activeNav, setActiveNav] = useState('dashboard');
  const [clock, setClock] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const utc = now.toUTCString().slice(17, 25);
      setClock(`UTC ${utc}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={styles.root}>
      {/* ── Top status bar ─────────────────────────────────────────────── */}
      <header style={styles.topBar}>
        <div style={styles.topBarLeft}>
          <span style={styles.logo}>▲ GALIL</span>
          <span style={styles.topBarDivider} />
          <span style={styles.topBarLabel}>AUTOMATED TRADING SYSTEM</span>
          <span style={styles.topBarDivider} />
          <span
            style={{
              ...styles.topBarLabel,
              color: '#00C853',
              fontFamily: 'monospace',
            }}
          >
            ● LIVE
          </span>
        </div>

        {/* Ticker strip */}
        <div style={styles.tickerStrip}>
          {TICKERS.map((t) => (
            <span key={t.sym} style={styles.tickerItem}>
              <span style={styles.tickerSym}>{t.sym}</span>
              <span style={styles.tickerPrice}>{t.price}</span>
              <span
                style={{
                  ...styles.tickerChg,
                  color: t.up ? '#00C853' : '#FF3B47',
                }}
              >
                {t.chg}
              </span>
            </span>
          ))}
        </div>

        <div style={styles.topBarRight}>
          <span style={styles.clock}>{clock}</span>
        </div>
      </header>

      {/* ── Main 3-column layout ───────────────────────────────────────── */}
      <div style={styles.body}>
        {/* LEFT: Navigation sidebar */}
        <nav style={styles.sidebar}>
          <div style={styles.sidebarInner}>
            {NAV_ITEMS.map(({ id, label, Icon }) => (
              <button
                key={id}
                style={{
                  ...styles.navBtn,
                  ...(activeNav === id ? styles.navBtnActive : {}),
                }}
                onClick={() => setActiveNav(id)}
                title={label}
              >
                <Icon active={activeNav === id} />
                <span
                  style={{
                    ...styles.navLabel,
                    color: activeNav === id ? '#1E90FF' : '#444',
                  }}
                >
                  {label}
                </span>
              </button>
            ))}
          </div>

          {/* Bottom system status */}
          <div style={styles.sidebarBottom}>
            <div style={styles.sysRow}>
              <span style={styles.sysDot} />
              <span style={styles.sysText}>API</span>
            </div>
            <div style={styles.sysRow}>
              <span style={{ ...styles.sysDot, background: '#00C853' }} />
              <span style={styles.sysText}>WS</span>
            </div>
            <div style={styles.sysRow}>
              <span style={{ ...styles.sysDot, background: '#FFB300' }} />
              <span style={styles.sysText}>DB</span>
            </div>
          </div>
        </nav>

        {/* CENTER: Command center */}
        <main style={styles.center}>
          {/* Chart panel */}
          <section style={styles.chartPanel}>
            <div style={styles.panelHeader}>
              <div style={styles.panelHeaderLeft}>
                <span style={styles.panelTitle}>XAUUSD</span>
                <span style={styles.panelSubtitle}>
                  GOLD / USD · M5 · OANDA
                </span>
                <span style={{ ...styles.liveChip, marginLeft: 12 }}>
                  <span style={styles.liveDot} />
                  LIVE
                </span>
              </div>
              <div style={styles.panelHeaderRight}>
                {['M1', 'M5', 'M15', 'H1', 'H4', 'D1'].map((tf, i) => (
                  <button
                    key={tf}
                    style={{
                      ...styles.tfBtn,
                      ...(i === 1 ? styles.tfBtnActive : {}),
                    }}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
            <div style={styles.chartArea}>
              <CandlestickChart />
            </div>
          </section>

          {/* Active Positions panel */}
          <section style={styles.positionsPanel}>
            <div style={styles.panelHeader}>
              <div style={styles.panelHeaderLeft}>
                <span style={styles.panelTitle}>ACTIVE POSITIONS</span>
                <span style={styles.posCount}>6 OPEN</span>
              </div>
              <div style={styles.panelHeaderRight}>
                <span style={styles.pnlTotal}>
                  NET P&amp;L&nbsp;
                  <span style={{ color: '#00C853' }}>+$1,842.50</span>
                </span>
              </div>
            </div>
            <ActivePositionsTable />
          </section>
        </main>

        {/* RIGHT: System status column */}
        <aside style={styles.rightCol}>
          {/* Wallet / Margin */}
          <section style={styles.walletPanel}>
            <div style={styles.panelHeader}>
              <span style={styles.panelTitle}>WALLET / MARGIN</span>
            </div>
            <WalletMargin />
          </section>

          {/* Execution log */}
          <section style={styles.logPanel}>
            <div style={styles.panelHeader}>
              <div style={styles.panelHeaderLeft}>
                <span style={styles.panelTitle}>EXECUTION LOG</span>
                <span style={{ ...styles.liveChip, marginLeft: 8 }}>
                  <span style={styles.liveDot} />
                  STREAM
                </span>
              </div>
            </div>
            <ExecutionLog />
          </section>
        </aside>
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const BORDER = '1px solid #1a1a1a';
const BG = '#0A0A0A';
const PANEL_BG = '#0A0A0A';
const HEADER_H = 36;
const SIDEBAR_W = 64;
const RIGHT_W = 300;

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    width: '100vw',
    height: '100vh',
    background: BG,
    color: '#e0e0e0',
    fontFamily: "'SF Pro Text', 'Segoe UI', system-ui, sans-serif",
    overflow: 'hidden',
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 9999,
  },

  // ── Top bar
  topBar: {
    display: 'flex',
    alignItems: 'center',
    height: HEADER_H,
    minHeight: HEADER_H,
    background: '#080808',
    borderBottom: BORDER,
    padding: '0 12px',
    gap: 0,
    flexShrink: 0,
  },
  topBarLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexShrink: 0,
    width: SIDEBAR_W + 180,
  },
  logo: {
    fontFamily: 'monospace',
    fontSize: 13,
    fontWeight: 700,
    color: '#1E90FF',
    letterSpacing: '0.12em',
  },
  topBarDivider: {
    width: 1,
    height: 14,
    background: '#222',
    display: 'inline-block',
  },
  topBarLabel: {
    fontFamily: 'monospace',
    fontSize: 10,
    color: '#444',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
  },
  tickerStrip: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    gap: 0,
    overflow: 'hidden',
    borderLeft: BORDER,
    borderRight: BORDER,
    height: '100%',
    paddingLeft: 8,
  },
  tickerItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    paddingRight: 16,
    borderRight: '1px solid #141414',
    marginRight: 16,
    height: '100%',
    flexShrink: 0,
  },
  tickerSym: {
    fontFamily: 'monospace',
    fontSize: 10,
    color: '#555',
    letterSpacing: '0.06em',
  },
  tickerPrice: {
    fontFamily: 'monospace',
    fontSize: 11,
    color: '#ccc',
    fontWeight: 600,
  },
  tickerChg: {
    fontFamily: 'monospace',
    fontSize: 10,
  },
  topBarRight: {
    flexShrink: 0,
    width: RIGHT_W,
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  clock: {
    fontFamily: 'monospace',
    fontSize: 11,
    color: '#444',
    letterSpacing: '0.08em',
  },

  // ── Body
  body: {
    display: 'flex',
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
  },

  // ── Sidebar
  sidebar: {
    width: SIDEBAR_W,
    minWidth: SIDEBAR_W,
    background: '#080808',
    borderRight: BORDER,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    flexShrink: 0,
  },
  sidebarInner: {
    display: 'flex',
    flexDirection: 'column',
    paddingTop: 8,
  },
  navBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    width: '100%',
    padding: '12px 0',
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    borderLeft: '2px solid transparent',
    transition: 'border-color 0.15s, background 0.15s',
  },
  navBtnActive: {
    borderLeft: '2px solid #1E90FF',
    background: 'rgba(30,144,255,0.06)',
  },
  navLabel: {
    fontFamily: 'monospace',
    fontSize: 8,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  sidebarBottom: {
    padding: '12px 0',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
    borderTop: BORDER,
  },
  sysRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
  },
  sysDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#00C853',
    flexShrink: 0,
  },
  sysText: {
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#444',
    letterSpacing: '0.06em',
  },

  // ── Center
  center: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    borderRight: BORDER,
    overflow: 'hidden',
  },

  // Chart panel
  chartPanel: {
    flex: '0 0 58%',
    display: 'flex',
    flexDirection: 'column',
    borderBottom: BORDER,
    overflow: 'hidden',
  },
  chartArea: {
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
    background: PANEL_BG,
  },

  // Positions panel
  positionsPanel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },

  // ── Panel header (shared)
  panelHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 34,
    minHeight: 34,
    padding: '0 12px',
    borderBottom: BORDER,
    background: '#080808',
    flexShrink: 0,
  },
  panelHeaderLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  panelHeaderRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  panelTitle: {
    fontFamily: 'monospace',
    fontSize: 10,
    color: '#555',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    fontWeight: 600,
  },
  panelSubtitle: {
    fontFamily: 'monospace',
    fontSize: 9,
    color: '#333',
    letterSpacing: '0.06em',
  },
  liveChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '1px 6px',
    border: '1px solid #1a1a1a',
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#00C853',
    letterSpacing: '0.1em',
  },
  liveDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: '#00C853',
    display: 'inline-block',
    animation: 'pulse 2s infinite',
  },
  tfBtn: {
    background: 'transparent',
    border: '1px solid #1a1a1a',
    color: '#444',
    fontFamily: 'monospace',
    fontSize: 9,
    padding: '2px 7px',
    cursor: 'pointer',
    letterSpacing: '0.06em',
  },
  tfBtnActive: {
    background: 'rgba(30,144,255,0.12)',
    border: '1px solid #1E90FF',
    color: '#1E90FF',
  },
  posCount: {
    fontFamily: 'monospace',
    fontSize: 9,
    color: '#1E90FF',
    border: '1px solid #1a2a3a',
    padding: '1px 6px',
    letterSpacing: '0.08em',
  },
  pnlTotal: {
    fontFamily: 'monospace',
    fontSize: 10,
    color: '#444',
    letterSpacing: '0.06em',
  },

  // ── Right column
  rightCol: {
    width: RIGHT_W,
    minWidth: RIGHT_W,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    flexShrink: 0,
  },
  walletPanel: {
    flex: '0 0 auto',
    borderBottom: BORDER,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  logPanel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
};
