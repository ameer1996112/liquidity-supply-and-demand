import { TradingSignal, getPnl, getSymbol } from '@/types/trading';
import { format, subDays, isAfter, getDay, startOfDay } from 'date-fns';

export interface CopilotMessage {
  role: 'user' | 'assistant';
  content: string;
  data?: CopilotResponseData;
  timestamp: Date;
}

export interface CopilotResponseData {
  type: 'table' | 'stat-cards' | 'signal-list' | 'text';
  statCards?: { label: string; value: string; color?: string }[];
  signals?: TradingSignal[];
  tableRows?: { key: string; value: string; color?: string }[];
}

export interface CopilotResponse {
  text: string;
  data?: CopilotResponseData;
}

const SESSION_NAMES: Record<number, string> = {
  0: 'Asia',
  1: 'London',
  2: 'New York',
  3: 'Off-Session',
};
const DAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function closedSignals(signals: TradingSignal[]): TradingSignal[] {
  return signals.filter((s) => {
    const st = (s.status || '').toLowerCase();
    return (st === 'closed' || st === 'executed') && getPnl(s) != null;
  });
}

function fmt$(n: number): string {
  return `${n >= 0 ? '+' : ''}$${Math.abs(n).toFixed(2)}`;
}

function winRate(trades: TradingSignal[]): number {
  const closed = trades.filter((s) => getPnl(s) != null);
  if (!closed.length) return 0;
  const wins = closed.filter((s) => (getPnl(s) ?? 0) > 0).length;
  return (wins / closed.length) * 100;
}

function totalPnl(trades: TradingSignal[]): number {
  return trades.reduce((acc, s) => acc + (getPnl(s) ?? 0), 0);
}

// ── Intent Detection ──────────────────────────────────────────────────────────

type Intent =
  | 'rejection_reason'
  | 'best_setups'
  | 'worst_setups'
  | 'win_rate_by_symbol'
  | 'win_rate_by_session'
  | 'win_rate_by_day'
  | 'win_rate_by_model'
  | 'recent_trades'
  | 'daily_summary'
  | 'pnl_summary'
  | 'worst_day'
  | 'best_day'
  | 'friday_trades'
  | 'symbol_query'
  | 'count_trades'
  | 'sharpe'
  | 'unknown';

function detectIntent(query: string): {
  intent: Intent;
  symbol?: string;
  days?: number;
} {
  const q = query.toLowerCase();

  if (q.match(/reject|filter|block|why.*not|not.*taken|skip/))
    return { intent: 'rejection_reason' };
  if (q.match(/best setup|top setup|best trade|highest pnl|most profitable/))
    return { intent: 'best_setups' };
  if (q.match(/worst setup|worst trade|biggest loss|most loss/))
    return { intent: 'worst_setups' };
  if (q.match(/win rate.*symbol|symbol.*win rate|by symbol|per symbol/))
    return { intent: 'win_rate_by_symbol' };
  if (q.match(/win rate.*session|session.*win rate|by session|per session/))
    return { intent: 'win_rate_by_session' };
  if (q.match(/win rate.*day|day.*win rate|by day|per day|day of week/))
    return { intent: 'win_rate_by_day' };
  if (q.match(/win rate.*model|model.*win rate|by model|per model|entry model/))
    return { intent: 'win_rate_by_model' };
  if (q.match(/friday/)) return { intent: 'friday_trades' };
  if (q.match(/worst day|worst session|worst.*date/))
    return { intent: 'worst_day' };
  if (q.match(/best day|best session|best.*date/))
    return { intent: 'best_day' };
  if (q.match(/recent|last (\d+) trade|latest/)) {
    const m = q.match(/last (\d+)/);
    return { intent: 'recent_trades', days: m ? parseInt(m[1]) : 10 };
  }
  if (q.match(/today|this week|this month|daily|summary/))
    return { intent: 'daily_summary' };
  if (q.match(/pnl|profit|loss|total|how much/))
    return { intent: 'pnl_summary' };
  if (q.match(/how many|count|number of/)) return { intent: 'count_trades' };
  if (q.match(/sharpe|sortino|ratio|risk.adjusted/))
    return { intent: 'sharpe' };

  // Symbol-specific query
  const symbols = [
    'xauusd',
    'eurusd',
    'gbpusd',
    'usdjpy',
    'gbpjpy',
    'nas100',
    'us100',
    'btcusd',
    'ethusd',
  ];
  for (const sym of symbols) {
    if (q.includes(sym))
      return { intent: 'symbol_query', symbol: sym.toUpperCase() };
  }

  return { intent: 'unknown' };
}

// ── Query Handlers ────────────────────────────────────────────────────────────

function handleRejectionReason(signals: TradingSignal[]): CopilotResponse {
  const rejected = signals
    .filter((s) => {
      const st = (s.status || '').toLowerCase();
      return st === 'ai_rejected' || st === 'filtered';
    })
    .slice(0, 5);

  if (!rejected.length) {
    return { text: '✅ No rejected signals found in the current dataset.' };
  }

  const rows = rejected.map((s) => {
    let reason = s.filter_reason || '';
    if (!reason && s.ai_reasoning) {
      const ai =
        typeof s.ai_reasoning === 'string'
          ? (() => {
              try {
                return JSON.parse(s.ai_reasoning);
              } catch {
                return {};
              }
            })()
          : s.ai_reasoning;
      reason =
        ((ai as Record<string, unknown>).reason as string) ||
        ((ai as Record<string, unknown>).narrative as string) ||
        'AI veto';
    }
    return {
      key: `${getSymbol(s)} ${format(new Date(s.created_at), 'MMM dd HH:mm')}`,
      value: reason || 'No reason recorded',
    };
  });

  return {
    text: `Found **${rejected.length}** rejected signals. Here are the most recent reasons:`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleBestSetups(
  signals: TradingSignal[],
  worst = false,
): CopilotResponse {
  const closed = closedSignals(signals)
    .sort((a, b) =>
      worst
        ? (getPnl(a) ?? 0) - (getPnl(b) ?? 0)
        : (getPnl(b) ?? 0) - (getPnl(a) ?? 0),
    )
    .slice(0, 5);

  if (!closed.length) return { text: 'No closed trades found yet.' };

  const label = worst ? 'worst' : 'best';
  return {
    text: `Here are your **${label} 5 trades**:`,
    data: { type: 'signal-list', signals: closed },
  };
}

function handleWinRateBySymbol(signals: TradingSignal[]): CopilotResponse {
  const closed = closedSignals(signals);
  const map = new Map<string, { wins: number; total: number; pnl: number }>();

  for (const s of closed) {
    const sym = getSymbol(s);
    const pnl = getPnl(s) ?? 0;
    const entry = map.get(sym) || { wins: 0, total: 0, pnl: 0 };
    entry.total++;
    entry.pnl += pnl;
    if (pnl > 0) entry.wins++;
    map.set(sym, entry);
  }

  const rows = Array.from(map.entries())
    .sort((a, b) => b[1].total - a[1].total)
    .map(([sym, d]) => ({
      key: sym,
      value: `${((d.wins / d.total) * 100).toFixed(1)}% WR · ${d.total} trades · ${fmt$(d.pnl)}`,
      color: d.pnl >= 0 ? '#0ecb81' : '#f6465d',
    }));

  if (!rows.length) return { text: 'No closed trades found.' };
  return {
    text: `**Win rate by symbol** (${closed.length} closed trades):`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleWinRateBySession(signals: TradingSignal[]): CopilotResponse {
  const closed = closedSignals(signals);
  const map = new Map<number, { wins: number; total: number; pnl: number }>();

  for (const s of closed) {
    const sess =
      s.session ??
      (s.ai_reasoning && typeof s.ai_reasoning !== 'string'
        ? ((s.ai_reasoning as Record<string, unknown>).session as number)
        : null);
    if (sess == null) continue;
    const pnl = getPnl(s) ?? 0;
    const entry = map.get(sess) || { wins: 0, total: 0, pnl: 0 };
    entry.total++;
    entry.pnl += pnl;
    if (pnl > 0) entry.wins++;
    map.set(sess, entry);
  }

  const rows = Array.from(map.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([sess, d]) => ({
      key: SESSION_NAMES[sess] || `Session ${sess}`,
      value: `${((d.wins / d.total) * 100).toFixed(1)}% WR · ${d.total} trades · ${fmt$(d.pnl)}`,
      color: d.pnl >= 0 ? '#0ecb81' : '#f6465d',
    }));

  if (!rows.length) return { text: 'No session data found on closed trades.' };
  return {
    text: `**Win rate by session:**`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleWinRateByDay(signals: TradingSignal[]): CopilotResponse {
  const closed = closedSignals(signals);
  const map = new Map<number, { wins: number; total: number; pnl: number }>();

  for (const s of closed) {
    const day = getDay(new Date(s.created_at));
    const pnl = getPnl(s) ?? 0;
    const entry = map.get(day) || { wins: 0, total: 0, pnl: 0 };
    entry.total++;
    entry.pnl += pnl;
    if (pnl > 0) entry.wins++;
    map.set(day, entry);
  }

  const rows = Array.from(map.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([day, d]) => ({
      key: DAY_NAMES[day],
      value: `${((d.wins / d.total) * 100).toFixed(1)}% WR · ${d.total} trades · ${fmt$(d.pnl)}`,
      color: d.pnl >= 0 ? '#0ecb81' : '#f6465d',
    }));

  if (!rows.length) return { text: 'No closed trades found.' };
  return {
    text: `**Win rate by day of week:**`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleWinRateByModel(signals: TradingSignal[]): CopilotResponse {
  const closed = closedSignals(signals);
  const map = new Map<string, { wins: number; total: number; pnl: number }>();

  for (const s of closed) {
    const model =
      s.entry_model ||
      (s.ai_reasoning && typeof s.ai_reasoning !== 'string'
        ? ((s.ai_reasoning as Record<string, unknown>).entry_model as string)
        : null) ||
      'Unknown';
    const pnl = getPnl(s) ?? 0;
    const entry = map.get(model) || { wins: 0, total: 0, pnl: 0 };
    entry.total++;
    entry.pnl += pnl;
    if (pnl > 0) entry.wins++;
    map.set(model, entry);
  }

  const rows = Array.from(map.entries())
    .sort((a, b) => b[1].total - a[1].total)
    .map(([model, d]) => ({
      key: model.toUpperCase(),
      value: `${((d.wins / d.total) * 100).toFixed(1)}% WR · ${d.total} trades · ${fmt$(d.pnl)}`,
      color: d.pnl >= 0 ? '#0ecb81' : '#f6465d',
    }));

  if (!rows.length) return { text: 'No model data found.' };
  return {
    text: `**Win rate by entry model:**`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleFridayTrades(signals: TradingSignal[]): CopilotResponse {
  const fridays = closedSignals(signals).filter(
    (s) => getDay(new Date(s.created_at)) === 5,
  );
  if (!fridays.length)
    return { text: 'No Friday trades found in the dataset.' };

  const wr = winRate(fridays);
  const pnl = totalPnl(fridays);

  return {
    text: `📅 **Friday trades:** ${fridays.length} trades, ${wr.toFixed(1)}% win rate, ${fmt$(pnl)} total PnL.\n\n${pnl < 0 ? '⚠️ You tend to lose on Fridays. Consider avoiding Friday entries.' : '✅ Fridays are profitable for you!'}`,
    data: { type: 'signal-list', signals: fridays.slice(0, 5) },
  };
}

function handleDailySummary(signals: TradingSignal[]): CopilotResponse {
  const today = startOfDay(new Date());
  const todayTrades = closedSignals(signals).filter((s) =>
    isAfter(new Date(s.created_at), today),
  );
  const weekTrades = closedSignals(signals).filter((s) =>
    isAfter(new Date(s.created_at), subDays(new Date(), 7)),
  );

  const statCards = [
    {
      label: "Today's Trades",
      value: `${todayTrades.length}`,
      color: '#3b82f6',
    },
    {
      label: "Today's PnL",
      value: fmt$(totalPnl(todayTrades)),
      color: totalPnl(todayTrades) >= 0 ? '#0ecb81' : '#f6465d',
    },
    {
      label: "Today's WR",
      value: `${winRate(todayTrades).toFixed(1)}%`,
      color: winRate(todayTrades) >= 50 ? '#0ecb81' : '#f6465d',
    },
    { label: 'Week Trades', value: `${weekTrades.length}`, color: '#3b82f6' },
    {
      label: 'Week PnL',
      value: fmt$(totalPnl(weekTrades)),
      color: totalPnl(weekTrades) >= 0 ? '#0ecb81' : '#f6465d',
    },
    {
      label: 'Week WR',
      value: `${winRate(weekTrades).toFixed(1)}%`,
      color: winRate(weekTrades) >= 50 ? '#0ecb81' : '#f6465d',
    },
  ];

  return {
    text: `📊 **Daily & Weekly Summary:**`,
    data: { type: 'stat-cards', statCards },
  };
}

function handlePnlSummary(signals: TradingSignal[]): CopilotResponse {
  const closed = closedSignals(signals);
  const pnl = totalPnl(closed);
  const wr = winRate(closed);
  const wins = closed.filter((s) => (getPnl(s) ?? 0) > 0);
  const losses = closed.filter((s) => (getPnl(s) ?? 0) < 0);
  const avgWin = wins.length ? totalPnl(wins) / wins.length : 0;
  const avgLoss = losses.length
    ? Math.abs(totalPnl(losses)) / losses.length
    : 0;
  const pf = avgLoss > 0 ? totalPnl(wins) / Math.abs(totalPnl(losses)) : 0;

  const statCards = [
    {
      label: 'Total PnL',
      value: fmt$(pnl),
      color: pnl >= 0 ? '#0ecb81' : '#f6465d',
    },
    {
      label: 'Win Rate',
      value: `${wr.toFixed(1)}%`,
      color: wr >= 50 ? '#0ecb81' : '#f6465d',
    },
    {
      label: 'Profit Factor',
      value: pf.toFixed(2),
      color: pf >= 1.5 ? '#0ecb81' : pf >= 1 ? '#f0b90b' : '#f6465d',
    },
    { label: 'Avg Win', value: `+$${avgWin.toFixed(2)}`, color: '#0ecb81' },
    { label: 'Avg Loss', value: `-$${avgLoss.toFixed(2)}`, color: '#f6465d' },
    { label: 'Total Trades', value: `${closed.length}`, color: '#848e9c' },
  ];

  return {
    text: `💰 **PnL Summary** across ${closed.length} closed trades:`,
    data: { type: 'stat-cards', statCards },
  };
}

function handleSymbolQuery(
  signals: TradingSignal[],
  symbol: string,
): CopilotResponse {
  const symSignals = closedSignals(signals).filter((s) =>
    getSymbol(s).toUpperCase().includes(symbol),
  );
  if (!symSignals.length)
    return { text: `No closed trades found for **${symbol}**.` };

  const pnl = totalPnl(symSignals);
  const wr = winRate(symSignals);

  const statCards = [
    {
      label: `${symbol} Trades`,
      value: `${symSignals.length}`,
      color: '#3b82f6',
    },
    {
      label: 'Win Rate',
      value: `${wr.toFixed(1)}%`,
      color: wr >= 50 ? '#0ecb81' : '#f6465d',
    },
    {
      label: 'Total PnL',
      value: fmt$(pnl),
      color: pnl >= 0 ? '#0ecb81' : '#f6465d',
    },
  ];

  return {
    text: `📈 **${symbol} Performance:**`,
    data: { type: 'stat-cards', statCards },
  };
}

function handleBestWorstDay(
  signals: TradingSignal[],
  worst = false,
): CopilotResponse {
  const closed = closedSignals(signals);
  const dayMap = new Map<string, { pnl: number; count: number }>();

  for (const s of closed) {
    const day = format(new Date(s.created_at), 'MMM dd, yyyy');
    const pnl = getPnl(s) ?? 0;
    const entry = dayMap.get(day) || { pnl: 0, count: 0 };
    entry.pnl += pnl;
    entry.count++;
    dayMap.set(day, entry);
  }

  const sorted = Array.from(dayMap.entries()).sort((a, b) =>
    worst ? a[1].pnl - b[1].pnl : b[1].pnl - a[1].pnl,
  );

  const label = worst ? 'worst' : 'best';
  if (!sorted.length) return { text: 'No trade history found.' };

  const rows = sorted.slice(0, 5).map(([day, d]) => ({
    key: day,
    value: `${fmt$(d.pnl)} · ${d.count} trades`,
    color: d.pnl >= 0 ? '#0ecb81' : '#f6465d',
  }));

  return {
    text: `📅 **Top 5 ${label} trading days:**`,
    data: { type: 'table', tableRows: rows },
  };
}

function handleRecentTrades(
  signals: TradingSignal[],
  count = 10,
): CopilotResponse {
  const recent = [...signals]
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    .slice(0, count);

  if (!recent.length) return { text: 'No recent trades found.' };

  return {
    text: `🕐 **Last ${recent.length} signals:**`,
    data: { type: 'signal-list', signals: recent },
  };
}

function handleCountTrades(signals: TradingSignal[]): CopilotResponse {
  const total = signals.length;
  const closed = closedSignals(signals).length;
  const active = signals.filter((s) =>
    ['active', 'open', 'executed'].includes((s.status || '').toLowerCase()),
  ).length;
  const rejected = signals.filter((s) =>
    ['ai_rejected', 'filtered'].includes((s.status || '').toLowerCase()),
  ).length;

  const statCards = [
    { label: 'Total Signals', value: `${total}`, color: '#848e9c' },
    { label: 'Closed Trades', value: `${closed}`, color: '#3b82f6' },
    { label: 'Active', value: `${active}`, color: '#0ecb81' },
    { label: 'Rejected/Filtered', value: `${rejected}`, color: '#f6465d' },
  ];

  return {
    text: `📊 **Signal Counts:**`,
    data: { type: 'stat-cards', statCards },
  };
}

// ── Main Entry Point ──────────────────────────────────────────────────────────

export function queryCopilot(
  query: string,
  signals: TradingSignal[],
): CopilotResponse {
  const { intent, symbol, days } = detectIntent(query);

  switch (intent) {
    case 'rejection_reason':
      return handleRejectionReason(signals);
    case 'best_setups':
      return handleBestSetups(signals, false);
    case 'worst_setups':
      return handleBestSetups(signals, true);
    case 'win_rate_by_symbol':
      return handleWinRateBySymbol(signals);
    case 'win_rate_by_session':
      return handleWinRateBySession(signals);
    case 'win_rate_by_day':
      return handleWinRateByDay(signals);
    case 'win_rate_by_model':
      return handleWinRateByModel(signals);
    case 'friday_trades':
      return handleFridayTrades(signals);
    case 'worst_day':
      return handleBestWorstDay(signals, true);
    case 'best_day':
      return handleBestWorstDay(signals, false);
    case 'daily_summary':
      return handleDailySummary(signals);
    case 'pnl_summary':
      return handlePnlSummary(signals);
    case 'symbol_query':
      return handleSymbolQuery(signals, symbol || '');
    case 'count_trades':
      return handleCountTrades(signals);
    case 'recent_trades':
      return handleRecentTrades(signals, days || 10);
    case 'sharpe': {
      const closed = closedSignals(signals);
      const pnls = closed.map((s) => getPnl(s) ?? 0);
      if (pnls.length < 5)
        return {
          text: 'Need at least 5 closed trades to compute Sharpe ratio.',
        };
      const avg = pnls.reduce((a, b) => a + b, 0) / pnls.length;
      const std = Math.sqrt(
        pnls.reduce((a, b) => a + (b - avg) ** 2, 0) / pnls.length,
      );
      const sharpe = std > 0 ? (avg / std) * Math.sqrt(252) : 0;
      return {
        text: `📐 **Risk-Adjusted Metrics:**`,
        data: {
          type: 'stat-cards',
          statCards: [
            {
              label: 'Annualized Sharpe',
              value: sharpe.toFixed(2),
              color:
                sharpe >= 1 ? '#0ecb81' : sharpe >= 0 ? '#f0b90b' : '#f6465d',
            },
            {
              label: 'Avg Trade PnL',
              value: `$${avg.toFixed(2)}`,
              color: avg >= 0 ? '#0ecb81' : '#f6465d',
            },
            {
              label: 'Trade StdDev',
              value: `$${std.toFixed(2)}`,
              color: '#848e9c',
            },
          ],
        },
      };
    }
    default:
      return {
        text: `🤔 I didn't quite understand that. Try asking:\n\n• "Show my best setups"\n• "Why was the last trade rejected?"\n• "Win rate by symbol"\n• "How did I do today?"\n• "Show XAUUSD trades"\n• "My worst day this month"`,
      };
  }
}

// ── Quick Action Chips ────────────────────────────────────────────────────────

export const QUICK_ACTIONS = [
  { label: '💰 PnL Summary', query: 'show my total PnL and profit factor' },
  { label: "📅 Today's Summary", query: 'show today and this week summary' },
  {
    label: '❌ Why Rejected?',
    query: 'why were my last signals rejected or filtered?',
  },
  { label: '🏆 Best Setups', query: 'show my best trades' },
  { label: '📊 By Symbol', query: 'win rate by symbol' },
  { label: '🕐 By Session', query: 'win rate by session' },
  { label: '📆 By Day', query: 'win rate by day of week' },
  { label: '📐 Sharpe Ratio', query: 'show my sharpe ratio' },
];
