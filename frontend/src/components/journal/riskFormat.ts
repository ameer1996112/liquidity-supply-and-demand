import { TradingSignal } from '@/types/trading';

const INDEX_SYMBOLS = ['NAS100', 'NAS', 'US30', 'SPX', 'US100', 'US500', 'UK100', 'GER', 'FRA', 'JPN225', 'AUS200'];
const CRYPTO_SYMBOLS = ['BTC', 'ETH', 'BCH', 'LTC', 'XRP', 'ADA', 'SOL', 'DOGE'];

export interface JournalRisk {
  riskUsd: number;
  slPips: number;
  pipValuePerLot: number;
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
  'symbol' | 'ticker' | 'price' | 'entry' | 'stop_loss' | 'sl' | 'position_size' | 'size'
>): JournalRisk | null {
  const symbol = signal.symbol || signal.ticker || '';
  const entry = signal.price ?? signal.entry;
  const stopLoss = signal.stop_loss ?? signal.sl;
  const lots = signal.position_size ?? signal.size;

  if (!symbol || entry == null || stopLoss == null || lots == null || lots <= 0) return null;

  const pipSize = getJournalPipSize(symbol);
  const slPips = Math.abs(entry - stopLoss) / pipSize;
  const pipValuePerLot = getJournalPipValuePerLot(symbol, entry);
  const riskUsd = slPips * pipValuePerLot * lots;

  if (!Number.isFinite(riskUsd) || riskUsd <= 0) return null;

  return {
    riskUsd,
    slPips,
    pipValuePerLot,
  };
}

export function formatJournalRisk(risk?: JournalRisk | null): string {
  if (!risk) return '--';
  return `$${risk.riskUsd.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
