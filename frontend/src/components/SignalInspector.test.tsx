/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react-dom/test-utils';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SignalInspector } from './SignalInspector';
import type { TradingSignal } from '@/types/trading';

describe('SignalInspector decision summary', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it('renders NO_GO summary and breakdown from decision_trace', () => {
    const signal: TradingSignal = {
      id: 'sig-1',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'ai_rejected',
      price: 2942.1,
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'RF probability 33.6% < 63% threshold',
        rf_prob: 0.336,
        rf_threshold: 0.63,
        decision_trace: {
          rf_probability_pct: 33.6,
          threshold_pct: 63,
          rules: [
            {
              rule_id: 'rf_threshold',
              passed: false,
              message: 'RF probability 33.6% < 63% threshold',
            },
          ],
          rejected_rule: {
            rule_id: 'rf_threshold',
            message: 'RF probability 33.6% < 63% threshold',
          },
        },
      },
    };

    act(() => {
      root.render(
        <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
      );
    });

    expect(document.body.textContent).toContain('Decision Summary');
    expect(document.body.textContent).toContain('NO_GO');
    expect(document.body.textContent).toContain('Decision Breakdown');
    expect(document.body.textContent).toContain('RF Gate:');
    expect(document.body.textContent).toContain('Show Debug');
  });
});
