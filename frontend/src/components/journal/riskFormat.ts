import { TradingSignal } from '@/types/trading';

const INDEX_SYMBOLS = ['NAS100', 'NAS', 'US30', 'SPX', 'US100', 'US500', 'UK100', 'GER', 'FRA', 'JPN225', 'AUS200'];
const CRYPTO_SYMBOLS = ['BTC', 'ETH', 'BCH', 'LTC', 'XRP', 'ADA', 'SOL', 'DOGE'];

export interface JournalRisk {
  riskUsd: number;
  slPips: number;
  spreadPips: number;
  effectiveSlPips: number;
  pipValuePerLot: number;
  source: 'stored' | 'estimated';
}

export function getJournalPipSize(symbol: string): number {
  const normalized = symbol.toUpperCase();
  if (INDEX_SYMBOLS.some((item) => normalized.includes(item))) return 1;
  if (CRYPTO_SYMBOLS.some((item) => normalized.includes(item))) return 1;
  if (normalized.includes('JPY')) return 0.01;
  if (
    normalized.includes('XAU') ||
    normalized.includes('GOLD') ||
    normalized.includes('XAG') ||
    normalized.includes('SILVER')
  ) {
    return 0.01;
  }
  return 0.0001;
}

export function getJournalPipValuePerLot(symbol: string, entry: number): number {
  const normalized = symbol.toUpperCase();
  const pipSize = getJournalPipSize(normalized);

  if (INDEX_SYMBOLS.some((item) => normalized.includes(item))) return 1;
  if (CRYPTO_SYMBOLS.some((item) => normalized.includes(item))) return 1;
  if (normalized.includes('JPY')) return entry > 0 ? (pipSize / entry) * 100000 : 10;
  if (normalized.includes('XAU') || normalized.includes('GOLD')) return pipSize * 100;
  if (normalized.includes('XAG') || normalized.includes('SILVER')) return pipSize * 5000;
  if (normalized.endsWith('USD') || normalized.slice(3).includes('USD')) return 10;
  return entry > 0 ? (pipSize * 100000) / entry : 10;
}

export function calculateJournalRisk(signal: Pick<
  TradingSignal,
  | 'symbol'
  | 'ticker'
  | 'price'
  | 'entry'
  | 'stop_loss'
  | 'sl'
  | 'position_size'
  | 'size'
  | 'risk_usd'
  | 'spread_pips'
  | 'effective_sl_pips'
  | 'pip_value_per_lot'
>): JournalRisk | null {
  const symbol = signal.symbol || signal.ticker || '';
  const entry = signal.price ?? signal.entry;
  const stopLoss = signal.stop_loss ?? signal.sl;
  const lots = signal.position_size ?? signal.size;

  if (!symbol || entry == null || stopLoss == null || lots == null || lots <= 0) return null;

  const pipSize = getJournalPipSize(symbol);
  const slPips = Math.abs(entry - stopLoss) / pipSize;
  const spreadPips = signal.spread_pips ?? 0;
  const effectiveSlPips = signal.effective_sl_pips ?? slPips + spreadPips;
  const pipValuePerLot = signal.pip_value_per_lot ?? getJournalPipValuePerLot(symbol, entry);
  const storedRiskUsd = signal.risk_usd != null && signal.risk_usd > 0 ? signal.risk_usd : null;
  const riskUsd = storedRiskUsd ?? effectiveSlPips * pipValuePerLot * lots;

  if (!Number.isFinite(riskUsd) || riskUsd <= 0) return null;

  return {
    riskUsd,
    slPips,
    spreadPips,
    effectiveSlPips,
    pipValuePerLot,
    source: storedRiskUsd != null ? 'stored' : 'estimated',
  };
}

export function formatJournalRisk(risk?: JournalRisk | null): string {
  if (!risk) return '--';
  return `$${risk.riskUsd.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatJournalRiskTitle(risk?: JournalRisk | null): string | undefined {
  if (!risk) return undefined;
  const sourceLabel = risk.source === 'stored' ? 'backend sizing' : 'estimated from journal fields';
  return [
    `Risk: ${formatJournalRisk(risk)} (${sourceLabel})`,
    `SL: ${risk.slPips.toFixed(1)} pips`,
    `Spread: ${risk.spreadPips.toFixed(1)} pips`,
    `Effective SL: ${risk.effectiveSlPips.toFixed(1)} pips`,
    `Pip value: $${risk.pipValuePerLot.toFixed(2)}/lot`,
  ].join(' | ');
}
