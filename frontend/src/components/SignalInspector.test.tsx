/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SignalInspector } from './SignalInspector';
import type { TradingSignal } from '@/types/trading';
import { fetchAiRunBySignal } from '@/lib/api';

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchAiRunBySignal: vi.fn(),
  };
});

describe('SignalInspector decision summary', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.mocked(fetchAiRunBySignal).mockResolvedValue(null);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    vi.clearAllMocks();
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

  it('renders setup zone screenshot when setup evidence has an image', () => {
    const signal: TradingSignal = {
      id: 'sig-setup',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'GBPJPY',
      side: 'sell',
      status: 'active',
      price: 215.6,
      zone_id: 17733,
      setup_evidence: {
        status: 'ok',
        focus_zone: { id: 17733, high: 215.8, low: 215.2 },
        focus_image: { url: 'http://provider.test/provider-artifacts/setup-17733.png' },
        reason: '',
      },
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const image = document.querySelector('img[alt="Zone setup screenshot"]') as HTMLImageElement | null;
    expect(document.body.textContent).toContain('Zone Setup Screenshot');
    expect(document.body.textContent).toContain('#17733');
    expect(image?.src).toBe('http://provider.test/provider-artifacts/setup-17733.png');
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

  it('shows pending AI memo placeholders as processing without fallback context', async () => {
    vi.mocked(fetchAiRunBySignal).mockResolvedValue({
      id: 10,
      correlation_id: 'corr-1',
      signal_id: 123,
      run_type: 'debate',
      analysis_mode: 'shadow_pretrade',
      recommendation: 'pending',
      confidence: 0,
      reason_codes: [],
      memo: '',
      votes: {},
      transcript: [],
      chart_context: {},
      pine_context: {},
      module_status: {},
      layered_output: {},
    });

    const signal: TradingSignal = {
      id: '123',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'closed',
      price: 1.35062,
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const memoTab = Array.from(document.querySelectorAll('button')).find((el) =>
      el.textContent?.includes('AI Memo')
    );
    expect(memoTab).toBeTruthy();

    await act(async () => {
      memoTab?.dispatchEvent(
        new MouseEvent('mousedown', { bubbles: true, button: 0 })
      );
      memoTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    for (let i = 0; i < 10 && document.body.textContent?.includes('Loading AI Memo'); i++) {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });
    }

    expect(document.body.textContent).toContain('Council is processing this signal');
    expect(document.body.textContent).not.toContain('unclear');
    expect(document.body.textContent).not.toContain('Setup evidence unavailable');
  });

  it('shows permission rejection as a no-trade execution outcome', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-rejected',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'trading_permission_rejected' as TradingSignal['status'],
      price: 1.35852,
      filter_reason: 'permission_file_missing:approved_candidates.json',
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'permission_file_missing:approved_candidates.json',
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

    expect(document.body.textContent).toContain('No Trade');
    expect(document.body.textContent).toContain('Permission Gate');
    expect(document.body.textContent).toContain('permission_file_missing:approved_candidates.json');
    expect(document.body.textContent).not.toContain('OPEN');
  });

  it('shows permission allowed without broker execution as no entry', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-allowed',
      created_at: '2026-05-08T08:40:02.000Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'trading_permission_allowed' as TradingSignal['status'],
      price: 4714.11,
      execution_source: 'signal_only',
      run_mode: 'LIVE',
      ai_reasoning: {
        decision: 'GO',
        reason: 'Permission allowed, broker execution not recorded.',
      },
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('No Entry');
    expect(document.body.textContent).toContain('Broker Execution');
    expect(document.body.textContent).toContain('Broker Execution [unknown]');
    expect(document.body.textContent).not.toContain('Broker Execution [skipped]');
    expect(document.body.textContent).toContain('broker execution not recorded');
    expect(document.body.textContent).not.toContain('Opened trade');
  });

  it('does not show empty operating-layer fallbacks for completed legacy memos', async () => {
    vi.mocked(fetchAiRunBySignal).mockResolvedValue({
      id: 11,
      correlation_id: 'corr-legacy',
      signal_id: 124,
      run_type: 'debate',
      analysis_mode: 'shadow_pretrade',
      recommendation: 'allow',
      confidence: 70,
      reason_codes: ['conservative_block'],
      memo: '[Council] Approved with caution.',
      votes: {
        bull: 'allow',
        bear: 'block',
        judge: 'allow',
      },
      transcript: [
        { role: 'risk_judge', content: 'Approved with caution.' },
      ],
      chart_context: {},
      pine_context: {},
      module_status: {},
      layered_output: {},
    });

    const signal: TradingSignal = {
      id: '124',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'closed',
      price: 1.35062,
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const memoTab = Array.from(document.querySelectorAll('button')).find((el) =>
      el.textContent?.includes('AI Memo')
    );
    expect(memoTab).toBeTruthy();

    await act(async () => {
      memoTab?.dispatchEvent(
        new MouseEvent('mousedown', { bubbles: true, button: 0 })
      );
      memoTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    for (let i = 0; i < 10 && document.body.textContent?.includes('Loading AI Memo'); i++) {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });
    }

    expect(document.body.textContent).toContain('Final Vote');
    expect(document.body.textContent).toContain('ALLOW');
    expect(document.body.textContent).toContain('Approved with caution.');
    expect(document.body.textContent).not.toContain('AI Operating Layer');
    expect(document.body.textContent).not.toContain('unclear');
    expect(document.body.textContent).not.toContain('Setup evidence unavailable');
  });

  it('renders the execution desk header and pipeline path visibly', () => {
    const signal: TradingSignal = {
      id: 'sig-desk',
      created_at: '2026-05-08T08:40:02.000Z',
      symbol: 'GBPNZD',
      side: 'buy',
      status: 'trading_permission_allowed' as TradingSignal['status'],
      price: 2.28225,
      run_mode: 'LIVE',
      execution_source: 'signal_only',
      ai_reasoning: {
        decision: 'GO',
        reason: 'Setup approved by AI.',
      },
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.querySelector('[data-testid="execution-desk-header"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="execution-path"]')).not.toBeNull();
    expect(document.body.textContent).toContain('No Entry');
    expect(document.body.textContent).toContain('Signal Received');
    expect(document.body.textContent).toContain('Broker Execution');
  });
});
