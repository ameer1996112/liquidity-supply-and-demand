export const EMPTY_VALUE = '—';

export function normalizeNegativeZero(
  value: number | null | undefined,
  epsilon: number = 0.0005
): number | null {
  if (value == null || Number.isNaN(value)) return null;
  return Math.abs(value) < epsilon ? 0 : value;
}

export function formatCurrency(
  value: number | null | undefined,
  opts: { decimals?: number; signed?: boolean; empty?: string } = {}
): string {
  const { decimals = 2, signed = false, empty = EMPTY_VALUE } = opts;
  const normalized = normalizeNegativeZero(value);
  if (normalized == null) return empty;

  const sign = signed ? (normalized > 0 ? '+' : normalized < 0 ? '-' : '') : '';
  return `${sign}$${Math.abs(normalized).toFixed(decimals)}`;
}

export function formatNumber(
  value: number | null | undefined,
  opts: { decimals?: number; empty?: string } = {}
): string {
  const { decimals = 2, empty = EMPTY_VALUE } = opts;
  const normalized = normalizeNegativeZero(value);
  if (normalized == null) return empty;
  return normalized.toFixed(decimals);
}

export function formatPercent(
  value: number | null | undefined,
  opts: { decimals?: number; signed?: boolean; empty?: string } = {}
): string {
  const { decimals = 1, signed = false, empty = EMPTY_VALUE } = opts;
  const normalized = normalizeNegativeZero(value);
  if (normalized == null) return empty;
  const sign = signed ? (normalized > 0 ? '+' : normalized < 0 ? '-' : '') : '';
  return `${sign}${Math.abs(normalized).toFixed(decimals)}%`;
}

export function formatPips(
  value: number | null | undefined,
  opts: { decimals?: number; signed?: boolean; empty?: string } = {}
): string {
  const { decimals = 1, signed = false, empty = EMPTY_VALUE } = opts;
  const normalized = normalizeNegativeZero(value);
  if (normalized == null) return empty;
  const sign = signed ? (normalized > 0 ? '+' : normalized < 0 ? '-' : '') : '';
  return `${sign}${Math.abs(normalized).toFixed(decimals)} pips`;
}

export function formatWinRateValue(
  winRatePct: number | null | undefined,
  totalTrades: number | null | undefined
): string {
  if (!totalTrades || totalTrades <= 0) return EMPTY_VALUE;
  if (winRatePct == null || !Number.isFinite(winRatePct)) return EMPTY_VALUE;
  return formatPercent(winRatePct, { decimals: 1 });
}

export function formatOptionalMetric(
  value: number | null | undefined,
  formatter: (num: number) => string,
  totalTrades?: number | null
): string {
  if (totalTrades != null && totalTrades <= 0) return EMPTY_VALUE;
  if (value == null || !Number.isFinite(value)) return EMPTY_VALUE;
  const normalized = normalizeNegativeZero(value);
  if (normalized == null) return EMPTY_VALUE;
  return formatter(normalized);
}
