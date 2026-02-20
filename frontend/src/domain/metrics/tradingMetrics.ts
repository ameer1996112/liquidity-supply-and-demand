import { getPnl } from '../../types/trading';
import type { TradingSignal } from '../../types/trading';

export type EmptyWinRateBehavior = 'dash' | 'zero';

function normalizeStatus(status: TradingSignal['status'] | undefined): string {
  return String(status || '').toLowerCase();
}

export function isSignalRejected(signal: TradingSignal): boolean {
  const status = normalizeStatus(signal.status);
  return (
    status === 'ai_rejected' ||
    status === 'filtered' ||
    status === 'failed' ||
    status === 'cancelled' ||
    status === 'error'
  );
}

export function getSignalPnl(signal: TradingSignal): number | null {
  const pnl = getPnl(signal);
  return typeof pnl === 'number' && Number.isFinite(pnl) ? pnl : null;
}

export function isSignalClosed(signal: TradingSignal): boolean {
  const status = normalizeStatus(signal.status);
  if (status === 'closed') return true;
  if (status !== 'executed' && status !== 'open') return false;

  return (
    signal.closed_at != null ||
    signal.exit_price != null ||
    getSignalPnl(signal) != null
  );
}

export function isSignalOpen(signal: TradingSignal): boolean {
  const status = normalizeStatus(signal.status);

  // Strict check for execution source verified records
  if (
    status === 'open' &&
    signal.execution_source === 'metaapi' &&
    signal.broker_position_id != null
  ) {
    return true;
  }

  // Fallback for older executed trades that haven't closed yet
  if (
    (status === 'active' || status === 'pending' || status === 'executed') &&
    !isSignalClosed(signal)
  ) {
    // Wait, backend previously used 'active'/'executed' mapped to OPEN, but the ghost bug was specifically these didn't have real execution
    // Let's rely on broker_position_id to confirm reality
    return signal.broker_position_id != null;
  }

  return false;
}

export function toPercentFromRatioOrPercent(
  value: number | null | undefined,
): number {
  if (value == null || !Number.isFinite(value)) return 0;
  // Supports both 0..1 ratios and 0..100 percentages from mixed sources.
  return value <= 1 ? value * 100 : value;
}

export function computeTradeKpis(signals: TradingSignal[]) {
  const closedTrades = signals.filter(isSignalClosed);
  const wins = closedTrades.filter((s) => (getSignalPnl(s) ?? 0) > 0).length;
  const losses = closedTrades.filter((s) => (getSignalPnl(s) ?? 0) < 0).length;
  const breakeven = closedTrades.length - wins - losses;
  const totalPnl = closedTrades.reduce(
    (sum, s) => sum + (getSignalPnl(s) ?? 0),
    0,
  );
  const winRatePct =
    closedTrades.length > 0 ? (wins / closedTrades.length) * 100 : null;

  return {
    closedTrades,
    totalTrades: closedTrades.length,
    wins,
    losses,
    breakeven,
    totalPnl,
    winRatePct,
  };
}

export function computeTodayPnl(
  signals: TradingSignal[],
  now: Date = new Date(),
): number {
  const dayStart = new Date(now);
  dayStart.setHours(0, 0, 0, 0);

  return signals
    .filter(isSignalClosed)
    .filter((signal) => {
      const stamp = signal.closed_at || signal.created_at;
      return new Date(stamp) >= dayStart;
    })
    .reduce((sum, signal) => sum + (getSignalPnl(signal) ?? 0), 0);
}

export function formatWinRate(
  winRatePct: number | null,
  totalTrades: number,
  emptyBehavior: EmptyWinRateBehavior = 'dash',
): string {
  if (!totalTrades || winRatePct == null || !Number.isFinite(winRatePct)) {
    return emptyBehavior === 'zero' ? '0.0%' : '—';
  }
  return `${winRatePct.toFixed(1)}%`;
}
