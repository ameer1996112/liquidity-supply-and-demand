import { getNotes, type TradingSignal } from '@/types/trading';
import { formatDistanceToNowStrict } from 'date-fns';

/**
 * Safe float conversion - prevents toFixed crashes on null/undefined values.
 *
 * @param val - The value to convert
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string or "--" for null values
 */
export function safeFloat(
  val: number | null | undefined,
  decimals: number = 2
): string {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return '--';
  }
  return val.toFixed(decimals);
}

/**
 * Treat tiny floating-point values as zero to avoid UI noise like "-0.00".
 */
export function normalizeSignedZero(
  val: number | null | undefined,
  epsilon: number = 0.0005
): number | null {
  if (val === null || val === undefined || Number.isNaN(val)) return null;
  return Math.abs(val) < epsilon ? 0 : val;
}

/**
 * Currency formatter for compact dashboard KPIs with stable sign handling.
 */
export function formatSignedCurrency(
  val: number | null | undefined,
  decimals: number = 2
): string {
  const normalized = normalizeSignedZero(val);
  if (normalized === null) return '—';
  const sign = normalized > 0 ? '+' : normalized < 0 ? '-' : '';
  return `${sign}$${Math.abs(normalized).toFixed(decimals)}`;
}

/**
 * Truncate text to specified length with ellipsis.
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 40)
 * @returns Truncated string
 */
export function truncateText(
  text: string | null | undefined,
  maxLength: number = 40
): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '…';
}

/**
 * Get display reason from signal (notes or filter_reason, truncated to 40 chars).
 */
export function getDisplayReason(signal: TradingSignal): string {
  const notes = getNotes(signal);
  const reason = notes || signal.filter_reason;
  return truncateText(reason, 40);
}

/**
 * Format relative time in compact form (e.g., "2m ago").
 */
export function formatRelativeTime(date: Date): string {
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

/**
 * Get the appropriate number of decimal places for a symbol's price.
 */
export function getPriceDecimals(symbol: string): number {
  if (symbol.includes('JPY')) return 3;
  if (symbol.includes('BTC')) return 2;
  return 5;
}
