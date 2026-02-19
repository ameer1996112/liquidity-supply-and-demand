'use client';

import { useState, useEffect } from 'react';

interface AccountData {
  name: string;
  balance: number;
  equity: number;
  margin: number;
  freeMargin: number;
  marginLevel: number;
  drawdown: number;
  dailyPnl: number;
  maxDailyLoss: number;
  maxDrawdown: number;
}

const ACCOUNTS: AccountData[] = [
  {
    name: 'FTMO-01',
    balance: 98_420.5,
    equity: 98_762.5,
    margin: 1_240.0,
    freeMargin: 97_522.5,
    marginLevel: 7964.7,
    drawdown: 1.58,
    dailyPnl: 342.0,
    maxDailyLoss: 5000,
    maxDrawdown: 10000,
  },
  {
    name: 'MFF-02',
    balance: 49_880.0,
    equity: 50_418.5,
    margin: 820.0,
    freeMargin: 49_598.5,
    marginLevel: 6148.6,
    drawdown: 0.24,
    dailyPnl: 538.5,
    maxDailyLoss: 2500,
    maxDrawdown: 5000,
  },
];

function Bar({
  value,
  max,
  color,
  warnAt,
}: {
  value: number;
  max: number;
  color: string;
  warnAt?: number;
}) {
  const pct = Math.min((value / max) * 100, 100);
  const isWarn = warnAt !== undefined && value >= warnAt;
  return (
    <div style={barStyles.track}>
      <div
        style={{
          ...barStyles.fill,
          width: `${pct}%`,
          background: isWarn ? '#FF3B47' : color,
        }}
      />
    </div>
  );
}

const barStyles: Record<string, React.CSSProperties> = {
  track: {
    width: '100%',
    height: 3,
    background: '#111',
    position: 'relative',
    overflow: 'hidden',
  },
  fill: {
    position: 'absolute',
    top: 0,
    left: 0,
    height: '100%',
    transition: 'width 0.4s ease',
  },
};

function fmt(n: number, decimals = 2) {
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function WalletMargin() {
  const [accounts, setAccounts] = useState<AccountData[]>(ACCOUNTS);
  const [activeAcc, setActiveAcc] = useState(0);

  // Simulate live equity fluctuation
  useEffect(() => {
    const id = setInterval(() => {
      setAccounts((prev) =>
        prev.map((a) => {
          const delta = (Math.random() - 0.48) * 12;
          const newEquity = a.equity + delta;
          const newDailyPnl = a.dailyPnl + delta;
          const newDrawdown = Math.max(
            0,
            ((a.balance - newEquity) / a.balance) * 100
          );
          return {
            ...a,
            equity: newEquity,
            dailyPnl: newDailyPnl,
            drawdown: newDrawdown,
            freeMargin: newEquity - a.margin,
            marginLevel: (newEquity / a.margin) * 100,
          };
        })
      );
    }, 2800);
    return () => clearInterval(id);
  }, []);

  const acc = accounts[activeAcc];
  const dailyUsedPct =
    (Math.abs(acc.dailyPnl < 0 ? acc.dailyPnl : 0) / acc.maxDailyLoss) * 100;
  const ddUsedPct =
    (acc.drawdown / ((acc.maxDrawdown / acc.balance) * 100)) * 100;

  return (
    <div style={styles.wrapper}>
      {/* Account tabs */}
      <div style={styles.tabs}>
        {accounts.map((a, i) => (
          <button
            key={a.name}
            style={{
              ...styles.tab,
              ...(i === activeAcc ? styles.tabActive : {}),
            }}
            onClick={() => setActiveAcc(i)}
          >
            {a.name}
          </button>
        ))}
      </div>

      {/* Main metrics grid */}
      <div style={styles.grid}>
        {/* Balance */}
        <div style={styles.metricBlock}>
          <span style={styles.metricLabel}>BALANCE</span>
          <span style={styles.metricValue}>${fmt(acc.balance)}</span>
        </div>
        {/* Equity */}
        <div style={styles.metricBlock}>
          <span style={styles.metricLabel}>EQUITY</span>
          <span
            style={{
              ...styles.metricValue,
              color: acc.equity >= acc.balance ? '#00C853' : '#FF3B47',
            }}
          >
            ${fmt(acc.equity)}
          </span>
        </div>
        {/* Margin */}
        <div style={styles.metricBlock}>
          <span style={styles.metricLabel}>MARGIN USED</span>
          <span style={styles.metricValue}>${fmt(acc.margin)}</span>
        </div>
        {/* Free Margin */}
        <div style={styles.metricBlock}>
          <span style={styles.metricLabel}>FREE MARGIN</span>
          <span style={{ ...styles.metricValue, color: '#888' }}>
            ${fmt(acc.freeMargin)}
          </span>
        </div>
      </div>

      {/* Margin level bar */}
      <div style={styles.barSection}>
        <div style={styles.barRow}>
          <span style={styles.barLabel}>MARGIN LEVEL</span>
          <span
            style={{
              ...styles.barVal,
              color:
                acc.marginLevel > 500
                  ? '#00C853'
                  : acc.marginLevel > 200
                  ? '#FFB300'
                  : '#FF3B47',
            }}
          >
            {fmt(acc.marginLevel, 1)}%
          </span>
        </div>
        <Bar
          value={Math.min(acc.marginLevel, 2000)}
          max={2000}
          color='#1E90FF'
          warnAt={1800}
        />
      </div>

      {/* Daily P&L */}
      <div style={styles.barSection}>
        <div style={styles.barRow}>
          <span style={styles.barLabel}>DAILY P&amp;L</span>
          <span
            style={{
              ...styles.barVal,
              color: acc.dailyPnl >= 0 ? '#00C853' : '#FF3B47',
            }}
          >
            {acc.dailyPnl >= 0 ? '+' : ''}${fmt(acc.dailyPnl)}
          </span>
        </div>
        <Bar
          value={Math.abs(acc.dailyPnl < 0 ? acc.dailyPnl : 0)}
          max={acc.maxDailyLoss}
          color='#00C853'
          warnAt={acc.maxDailyLoss * 0.8}
        />
        <div style={styles.barSubRow}>
          <span style={styles.barSubLabel}>
            LIMIT ${fmt(acc.maxDailyLoss, 0)}
          </span>
          <span
            style={{
              ...styles.barSubLabel,
              color: dailyUsedPct > 80 ? '#FF3B47' : '#2a2a2a',
            }}
          >
            {dailyUsedPct.toFixed(1)}% USED
          </span>
        </div>
      </div>

      {/* Drawdown */}
      <div style={styles.barSection}>
        <div style={styles.barRow}>
          <span style={styles.barLabel}>DRAWDOWN</span>
          <span
            style={{
              ...styles.barVal,
              color:
                acc.drawdown < 3
                  ? '#00C853'
                  : acc.drawdown < 7
                  ? '#FFB300'
                  : '#FF3B47',
            }}
          >
            {acc.drawdown.toFixed(2)}%
          </span>
        </div>
        <Bar
          value={acc.drawdown}
          max={(acc.maxDrawdown / acc.balance) * 100}
          color='#FFB300'
          warnAt={(acc.maxDrawdown / acc.balance) * 80}
        />
        <div style={styles.barSubRow}>
          <span style={styles.barSubLabel}>MAX ${fmt(acc.maxDrawdown, 0)}</span>
          <span
            style={{
              ...styles.barSubLabel,
              color: ddUsedPct > 80 ? '#FF3B47' : '#2a2a2a',
            }}
          >
            {ddUsedPct.toFixed(1)}% USED
          </span>
        </div>
      </div>

      {/* Prop firm rules summary */}
      <div style={styles.rulesSection}>
        <div style={styles.rulesHeader}>PROP FIRM RULES</div>
        {[
          {
            label: 'Daily Loss Limit',
            ok: Math.abs(Math.min(acc.dailyPnl, 0)) < acc.maxDailyLoss,
          },
          {
            label: 'Max Drawdown',
            ok: acc.drawdown < (acc.maxDrawdown / acc.balance) * 100,
          },
          { label: 'News Filter', ok: true },
          { label: 'Overnight Hold', ok: true },
          { label: 'Min Trading Days', ok: true },
        ].map((rule) => (
          <div key={rule.label} style={styles.ruleRow}>
            <span
              style={{
                ...styles.ruleDot,
                background: rule.ok ? '#00C853' : '#FF3B47',
                boxShadow: rule.ok ? '0 0 4px #00C853' : '0 0 4px #FF3B47',
              }}
            />
            <span style={styles.ruleLabel}>{rule.label}</span>
            <span
              style={{
                ...styles.ruleStatus,
                color: rule.ok ? '#00C853' : '#FF3B47',
              }}
            >
              {rule.ok ? 'PASS' : 'FAIL'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const BORDER = '1px solid #141414';

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    background: '#0A0A0A',
    overflow: 'hidden',
  },
  tabs: {
    display: 'flex',
    borderBottom: BORDER,
    flexShrink: 0,
  },
  tab: {
    flex: 1,
    height: 28,
    background: 'transparent',
    border: 'none',
    borderRight: BORDER,
    fontFamily: 'monospace',
    fontSize: 9,
    color: '#333',
    cursor: 'pointer',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    transition: 'color 0.15s, background 0.15s',
  },
  tabActive: {
    color: '#1E90FF',
    background: 'rgba(30,144,255,0.05)',
    borderBottom: '1px solid #1E90FF',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    borderBottom: BORDER,
  },
  metricBlock: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '8px 10px',
    borderRight: BORDER,
    borderBottom: BORDER,
  },
  metricLabel: {
    fontFamily: 'monospace',
    fontSize: 7,
    color: '#2a2a2a',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
  },
  metricValue: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#888',
    fontWeight: 600,
    letterSpacing: '0.04em',
  },
  barSection: {
    padding: '7px 10px',
    borderBottom: BORDER,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  barRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  barLabel: {
    fontFamily: 'monospace',
    fontSize: 7,
    color: '#2a2a2a',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
  },
  barVal: {
    fontFamily: 'monospace',
    fontSize: 10,
    fontWeight: 600,
  },
  barSubRow: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: 2,
  },
  barSubLabel: {
    fontFamily: 'monospace',
    fontSize: 7,
    color: '#2a2a2a',
    letterSpacing: '0.08em',
  },
  rulesSection: {
    padding: '6px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  rulesHeader: {
    fontFamily: 'monospace',
    fontSize: 7,
    color: '#2a2a2a',
    letterSpacing: '0.14em',
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  ruleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    height: 16,
  },
  ruleDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    flexShrink: 0,
  },
  ruleLabel: {
    fontFamily: 'monospace',
    fontSize: 8,
    color: '#333',
    flex: 1,
    letterSpacing: '0.04em',
  },
  ruleStatus: {
    fontFamily: 'monospace',
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: '0.08em',
  },
};
