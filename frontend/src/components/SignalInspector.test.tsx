/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const aiTab = Array.from(document.querySelectorAll('button')).find((el) =>
      el.textContent?.includes('AI Brain')
    );
    expect(aiTab).toBeTruthy();
    act(() => {
      aiTab?.dispatchEvent(
        new MouseEvent('mousedown', { bubbles: true, button: 0 })
      );
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('Decision Summary');
    expect(document.body.textContent).toContain('NO_GO');
    expect(document.body.textContent).toContain('Decision Breakdown');
    expect(document.body.textContent).toContain('RF Gate:');
    expect(document.body.textContent).toContain('Show Debug');
  });

  it('renders llm_context as SKIPPED (non-blocking) instead of PASS', () => {
    const signal: TradingSignal = {
      id: 'sig-2',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'XAUUSD',
      side: 'buy',
      status: 'active',
      price: 2942.1,
      ai_reasoning: {
        decision: 'GO',
        reason: 'RF pass; Context unavailable — treated as neutral.',
        llm_status: 'skipped',
        decision_trace: {
          rf_probability_pct: 72,
          threshold_pct: 60,
          rules: [
            {
              rule_id: 'rf_threshold',
              passed: true,
              message: 'RF probability 72.0% >= 60% threshold',
            },
            {
              rule_id: 'llm_context',
              status: 'skipped',
              passed: false,
              non_blocking: true,
              message: 'Context unavailable — treated as neutral.',
            },
          ],
        },
      },
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const aiTab = Array.from(document.querySelectorAll('button')).find((el) =>
      el.textContent?.includes('AI Brain')
    );
    expect(aiTab).toBeTruthy();
    act(() => {
      aiTab?.dispatchEvent(
        new MouseEvent('mousedown', { bubbles: true, button: 0 })
      );
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('LLM Context:');
    expect(document.body.textContent).toContain('SKIPPED');
    expect(document.body.textContent).toContain('llm_context');
    expect(document.body.textContent).not.toContain('llm_error');
  });

  it('shows execution plan for entry via MetaApi bridge', () => {
    const signal: TradingSignal = {
      id: 'sig-entry',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'NAS100',
      side: 'buy',
      status: 'active',
      price: 21500,
      execution_source: 'metaapi',
      run_mode: 'LIVE',
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('Execution Plan');
    expect(document.body.textContent).toContain('ENTRY');
    expect(document.body.textContent).toContain('MetaApi MT5 bridge');
  });

  it('shows execution plan for close_all action', () => {
    const signal: TradingSignal = {
      id: 'sig-close-all',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'active',
      price: 2942.1,
      execution_source: 'metaapi',
      run_mode: 'LIVE',
      signal_action: 'close_all',
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('Execution Plan');
    expect(document.body.textContent).toContain('CLOSE_ALL');
    expect(document.body.textContent).toContain('close all open positions');
  });
});
