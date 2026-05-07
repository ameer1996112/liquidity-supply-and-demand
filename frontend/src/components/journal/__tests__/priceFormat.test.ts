import { describe, expect, test } from 'vitest';
import { formatJournalPrice } from '../priceFormat';

describe('formatJournalPrice', () => {
  test('formats forex, JPY, and metal setup prices without currency or PnL signs', () => {
    expect(formatJournalPrice(2.28128, 'GBPNZD')).toBe('2.28128');
    expect(formatJournalPrice(157.05612, 'USDJPY')).toBe('157.056');
    expect(formatJournalPrice(4739.14, 'XAUUSD')).toBe('4739.14');
  });

  test('returns a stable placeholder for missing setup prices', () => {
    expect(formatJournalPrice(null, 'XAUUSD')).toBe('--');
    expect(formatJournalPrice(undefined, 'GBPNZD')).toBe('--');
  });
});
