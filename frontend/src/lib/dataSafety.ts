/**
 * Data Safety Utilities
 *
 * Centralized helpers to prevent NaN, undefined, and null display issues.
 * Use these throughout the app for consistent data validation.
 */

// ══════════════════════════════════════════════════════════
// Number Safety
// ══════════════════════════════════════════════════════════

/**
 * Safely format a number, returning fallback if NaN/null/undefined
 */
export function safeNumber(
  value: number | null | undefined,
  fallback: number = 0,
): number {
  if (value == null || !isFinite(value) || isNaN(value)) {
    return fallback;
  }
  return value;
}

/**
 * Safely format a number to fixed decimals
 */
export function safeFixed(
  value: number | null | undefined,
  decimals: number = 2,
  fallback: string = '0.00',
): string {
  const safe = safeNumber(value);
  if (safe === 0 && value == null) return fallback;
  return safe.toFixed(decimals);
}

/**
 * Safely calculate percentage (prevents division by zero)
 */
export function safePercentage(
  numerator: number | null | undefined,
  denominator: number | null | undefined,
  fallback: number = 0,
): number {
  const num = safeNumber(numerator);
  const den = safeNumber(denominator);

  if (den === 0) return fallback;
  return (num / den) * 100;
}

/**
 * Safely calculate win rate
 */
export function safeWinRate(
  wins: number | null | undefined,
  totalTrades: number | null | undefined,
): number {
  return safePercentage(wins, totalTrades, 0);
}

// ══════════════════════════════════════════════════════════
// Currency Formatting
// ══════════════════════════════════════════════════════════

/**
 * Format currency with $ sign
 */
export function formatCurrency(
  value: number | null | undefined,
  options?: {
    decimals?: number;
    includeSign?: boolean;
    fallback?: string;
  },
): string {
  const {
    decimals = 2,
    includeSign = false,
    fallback = '$0.00',
  } = options || {};

  const safe = safeNumber(value);
  if (safe === 0 && value == null) return fallback;

  const sign = includeSign && safe > 0 ? '+' : '';
  return `${sign}$${Math.abs(safe).toFixed(decimals)}`;
}

/**
 * Format P&L with color-coded sign
 */
export function formatPnL(
  value: number | null | undefined,
  decimals: number = 2,
): { text: string; isPositive: boolean; isZero: boolean } {
  const safe = safeNumber(value);
  const isPositive = safe > 0;
  const isZero = safe === 0;

  const sign = isPositive ? '+' : '';
  const text = `${sign}$${safe.toFixed(decimals)}`;

  return { text, isPositive, isZero };
}

// ══════════════════════════════════════════════════════════
// Percentage Formatting
// ══════════════════════════════════════════════════════════

/**
 * Format percentage with % sign
 */
export function formatPercentage(
  value: number | null | undefined,
  decimals: number = 1,
  fallback: string = '0.0%',
): string {
  const safe = safeNumber(value);
  if (safe === 0 && value == null) return fallback;
  return `${safe.toFixed(decimals)}%`;
}

// ══════════════════════════════════════════════════════════
// Array Safety
// ══════════════════════════════════════════════════════════

/**
 * Ensure array is not null/undefined
 */
export function safeArray<T>(value: T[] | null | undefined): T[] {
  return value || [];
}

/**
 * Get array length safely
 */
export function safeLength<T>(value: T[] | null | undefined): number {
  return safeArray(value).length;
}

// ══════════════════════════════════════════════════════════
// Empty State Helpers
// ══════════════════════════════════════════════════════════

/**
 * Check if data is empty (for empty state rendering)
 */
export function isEmpty<T>(value: T[] | null | undefined): boolean {
  return safeLength(value) === 0;
}

/**
 * Check if number data exists
 */
export function hasValue(value: number | null | undefined): boolean {
  return value != null && isFinite(value) && !isNaN(value);
}

// ══════════════════════════════════════════════════════════
// Chart Data Safety
// ══════════════════════════════════════════════════════════

/**
 * Ensure chart values are safe (no NaN or Infinity)
 */
export function safeChartValue(value: number | null | undefined): number {
  const safe = safeNumber(value, 0);
  // Clamp to reasonable range for charts
  return Math.max(-1000000, Math.min(1000000, safe));
}

/**
 * Filter out invalid chart data points
 */
export function sanitizeChartData<T extends Record<string, unknown>>(
  data: T[],
  valueKeys: string[],
): T[] {
  return data.filter((point) => {
    return valueKeys.every((key) => {
      const value = point[key];
      if (typeof value !== 'number') return true; // Allow non-number fields
      return isFinite(value) && !isNaN(value);
    });
  });
}
