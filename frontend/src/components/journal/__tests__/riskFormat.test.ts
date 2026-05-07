import { describe, expect, test } from 'vitest';
import { calculateJournalRisk, formatJournalRisk, formatJournalRiskTitle } from '../riskFormat';

describe('journal risk formatting', () => {
  test('calculates USD risk from JPY stop distance and lots', () => {
    const risk = calculateJournalRisk({
      symbol: 'USDJPY',
      entry: 156.404,
      sl: 156.503,
      size: 0.4,
    });

    expect(risk?.slPips).toBeCloseTo(9.9, 1);
    expect(risk?.riskUsd).toBeCloseTo(25.32, 2);
    expect(risk?.source).toBe('estimated');
    expect(formatJournalRisk(risk)).toBe('$25.32');
  });

  test('prefers stored backend sizing risk including spread and buffer', () => {
    const risk = calculateJournalRisk({
      symbol: 'USDJPY',
      entry: 156.404,
      sl: 156.503,
      size: 0.4,
      risk_usd: 30.44,
      spread_pips: 1.2,
      effective_sl_pips: 11.9,
      pip_value_per_lot: 6.3937,
    });

    expect(risk?.source).toBe('stored');
    expect(risk?.riskUsd).toBe(30.44);
    expect(risk?.spreadPips).toBe(1.2);
    expect(risk?.effectiveSlPips).toBe(11.9);
    expect(formatJournalRisk(risk)).toBe('$30.44');
    expect(formatJournalRiskTitle(risk)).toContain('backend sizing');
  });

  test('calculates metal risk using contract size per lot', () => {
    const risk = calculateJournalRisk({
      symbol: 'XAUUSD',
      entry: 4739.14,
      sl: 4745.11,
      size: 0.1,
    });

    expect(risk?.slPips).toBeCloseTo(597, 1);
    expect(risk?.riskUsd).toBeCloseTo(59.7, 2);
    expect(formatJournalRisk(risk)).toBe('$59.70');
  });

  test('returns placeholder when risk inputs are missing', () => {
    expect(calculateJournalRisk({ symbol: 'GBPUSD', entry: 1.25 })).toBeNull();
    expect(formatJournalRisk(null)).toBe('--');
  });
});
