import { getPnl, TradingSignal } from '@/types/trading';

export function normalizeSession(value: unknown): string {
  if (value == null) return 'Unknown';
  if (typeof value === 'number') {
    if (value === 0) return 'Asia';
    if (value === 1) return 'London';
    if (value === 2) return 'New York';
    if (value === 3) return 'Off-Session';
  }
  const s = String(value).toLowerCase();
  if (s.includes('asia')) return 'Asia';
  if (s.includes('london')) return 'London';
  if (s.includes('new') || s.includes('ny')) return 'New York';
  return String(value);
}

export function getSignalSession(signal: TradingSignal): string {
  const s = signal as TradingSignal & { session?: unknown };
  if (s.session != null) return normalizeSession(s.session);
  const ai = signal.ai_reasoning as unknown;
  if (
    ai &&
    typeof ai === 'object' &&
    'session' in (ai as Record<string, unknown>)
  ) {
    return normalizeSession((ai as Record<string, unknown>).session);
  }
  return 'Unknown';
}

export function getSignalAccount(signal: TradingSignal): string {
  const s = signal as TradingSignal & {
    account_name?: string;
    account?: string;
    account_id?: string;
  };
  return s.account_name || s.account || s.account_id || 'default';
}

export function isClosedSignal(signal: TradingSignal): boolean {
  const st = String(signal.status || '').toLowerCase();
  return (st === 'closed' || st === 'executed') && getPnl(signal) != null;
}

export function computeHealthScore(
  dailyPct: number,
  dailyLimit: number,
  trailingPct: number,
  trailingLimit: number,
  consistencyPct: number,
  consistencyLimit: number,
  safeToTrade: boolean,
  currentProfitPct: number
) {
  if (!safeToTrade) return 0;
  let score = 100;
  score -= (dailyPct / Math.max(dailyLimit, 0.01)) * 30;
  score -= (trailingPct / Math.max(trailingLimit, 0.01)) * 30;
  if (consistencyPct > consistencyLimit * 0.8) score -= 20;
  else if (consistencyPct > consistencyLimit * 0.6) score -= 10;
  if (currentProfitPct > 0) score += Math.min(currentProfitPct * 2, 10);
  return Math.max(0, Math.min(100, Math.round(score)));
}
