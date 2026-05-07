export function getJournalPriceDecimals(symbol?: string | null, value?: number | null): number {
  const normalized = (symbol || '').toUpperCase();

  if (normalized.includes('JPY')) return 3;
  if (
    normalized.includes('XAU') ||
    normalized.includes('BTC') ||
    normalized.includes('NAS') ||
    normalized.includes('US30') ||
    normalized.includes('SPX')
  ) {
    return 2;
  }

  if (value != null && Math.abs(value) >= 100) return 2;
  return 5;
}

export function formatJournalPrice(value?: number | null, symbol?: string | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(getJournalPriceDecimals(symbol, value));
}
