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

    expect(document.querySelector('[data-testid="ai-decision-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('AI Decision');
    expect(document.body.textContent).toContain('NO_GO');
    expect(document.body.textContent).toContain('rf_threshold');
    expect(document.body.textContent).toContain('RF probability 33.6% < 63% threshold');
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

  it('renders compact trade plan facts in the overview tab', () => {
    const signal: TradingSignal = {
      id: 'sig-plan',
      created_at: '2026-05-08T09:00:00.000Z',
      symbol: 'USDJPY',
      side: 'buy',
      status: 'active',
      entry: 156.659,
      sl: 156.579,
      tp: 156.859,
      risk_usd: 125.11,
      position_size: 0.4,
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

    expect(document.querySelector('[data-testid="trade-plan-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('Trade Plan');
    expect(document.body.textContent).toContain('Entry');
    expect(document.body.textContent).toContain('156.659');
    expect(document.body.textContent).toContain('Stop Loss');
    expect(document.body.textContent).toContain('156.579');
    expect(document.body.textContent).toContain('Take Profit');
    expect(document.body.textContent).toContain('156.859');
    expect(document.body.textContent).toContain('$125.11');
    expect(document.body.textContent).toContain('MetaApi MT5 bridge');
  });

  it('formats index prices without forex precision in the trade plan', () => {
    const signal: TradingSignal = {
      id: 'sig-index-plan',
      created_at: '2026-05-08T09:05:00.000Z',
      symbol: 'NAS100',
      side: 'buy',
      status: 'active',
      price: 21500,
      sl: 21450,
      tp: 21625.5,
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

    expect(document.querySelector('[data-testid="trade-plan-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('21500.00');
    expect(document.body.textContent).toContain('21450.00');
    expect(document.body.textContent).toContain('21625.50');
    expect(document.body.textContent).not.toContain('21500.00000');
  });

  it('restores compact RR, stop distance, PnL percent, and exit type facts', () => {
    const signal: TradingSignal = {
      id: 'sig-plan-details',
      created_at: '2026-05-08T09:10:00.000Z',
      symbol: 'NAS100',
      side: 'sell',
      status: 'closed',
      entry: 21500,
      sl: 21540,
      tp: 21400,
      rr_ratio: 2.5,
      sl_pips: 40,
      pnl_percentage: 1.75,
      exit_type: 'take_profit',
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

    expect(document.body.textContent).toContain('Risk:Reward');
    expect(document.body.textContent).toContain('1:2.50');
    expect(document.body.textContent).toContain('SL Distance');
    expect(document.body.textContent).toContain('40.0 pts');
    expect(document.body.textContent).toContain('PnL %');
    expect(document.body.textContent).toContain('+1.75%');
    expect(document.body.textContent).toContain('Exit Type');
    expect(document.body.textContent).toContain('take profit');
  });

  it('renders AI brain as diagnostic evidence with the failing reason preserved', () => {
    const signal: TradingSignal = {
      id: 'sig-ai-evidence',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'ai_rejected',
      price: 1.35852,
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'RF probability 33.6% < 63% threshold',
        llm_status: 'skipped',
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
    act(() => {
      aiTab?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.querySelector('[data-testid="ai-decision-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('AI Decision');
    expect(document.body.textContent).toContain('NO_GO');
    expect(document.body.textContent).toContain('RF probability 33.6% < 63% threshold');
    expect(document.body.textContent).toContain('LLM Context');
  });

  it('shows RF gate diagnostics from structured trace values without a rule message', () => {
    const signal: TradingSignal = {
      id: 'sig-rf-structured',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'ai_rejected',
      price: 1.35852,
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'Model threshold not met.',
        decision_trace: {
          rf_probability_pct: 33.6,
          threshold_pct: 63,
          rules: [
            {
              rule_id: 'rf_threshold',
              passed: false,
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
    act(() => {
      aiTab?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('RF Gate:');
    expect(document.body.textContent).toContain('33.6% vs 63.0% threshold');
  });

  it('keeps skipped LLM context visible for NO_GO when it is not the failing rule', () => {
    const signal: TradingSignal = {
      id: 'sig-llm-visible',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'ai_rejected',
      price: 1.35852,
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'RF probability 33.6% < 63% threshold',
        decision_trace: {
          rf_probability_pct: 33.6,
          threshold_pct: 63,
          rules: [
            {
              rule_id: 'rf_threshold',
              passed: false,
              message: 'RF probability 33.6% < 63% threshold',
            },
            {
              rule_id: 'llm_context',
              status: 'skipped',
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
    act(() => {
      aiTab?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('LLM Context:');
    expect(document.body.textContent).toContain('SKIPPED');
    expect(document.body.textContent).toContain('RF probability 33.6% < 63% threshold');
  });

  it('does not label legacy metric-only AI data as rejected', () => {
    const signal: TradingSignal = {
      id: 'sig-active-legacy-metrics',
      created_at: '2026-05-08T10:00:00.000Z',
      symbol: 'GBPUSD',
      side: 'buy',
      status: 'active',
      price: 1.35852,
      zone_id: 17862,
      zone_type: 'demand',
      zone_grade: 'B+',
    } as TradingSignal;

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
    act(() => {
      aiTab?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('AI Decision');
    expect(document.body.textContent).toContain('NOT RECORDED');
    expect(document.body.textContent).toContain('No AI decision was recorded for this signal.');
    expect(document.body.textContent).not.toContain('Rejected: No explicit rejection reason');
  });

  it('marks broker execution as failed when status failed even with broker source', () => {
    const signal: TradingSignal = {
      id: 'sig-exec-failed',
      created_at: '2026-05-08T10:05:00.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'failed',
      price: 1.35852,
      execution_source: 'metaapi',
      filter_reason: 'broker adapter timeout',
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('Exec Fail');
    expect(document.body.textContent).toContain('Broker Execution');
    expect(document.body.textContent).toContain('fail');
    expect(document.body.textContent).toContain('broker adapter timeout');
    expect(document.body.textContent).not.toContain('Broker execution is recorded.');
  });

  it('shows downstream stages skipped after permission gate stops the signal', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-stop-ai-reason',
      created_at: '2026-05-08T10:10:00.000Z',
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

    expect(document.body.textContent).toContain('Permission Gate');
    expect(document.body.textContent).toContain('AI Brain');
    expect(document.body.textContent).toContain('Skipped after permission gate stopped the signal.');
    expect(document.body.textContent).not.toContain('AI rejected this signal.');
  });

  it('shows broker-executed permission signals as open', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-allowed-executed',
      created_at: '2026-05-08T10:15:00.000Z',
      symbol: 'GBPUSD',
      side: 'buy',
      status: 'trading_permission_allowed' as TradingSignal['status'],
      price: 1.35852,
      execution_source: 'metaapi',
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('Open');
    expect(document.body.textContent).toContain('Broker Position Active');
    expect(document.body.textContent).toContain('Broker execution is recorded.');
    expect(document.body.textContent).not.toContain('Signal State');
  });

  it('shows AI-rejected exit signals with position impact as recorded', () => {
    const signal: TradingSignal = {
      id: 'sig-exit-ai-rejected-position-impact',
      created_at: '2026-05-08T10:55:02.000Z',
      symbol: 'XAUUSD',
      side: 'buy',
      status: 'ai_rejected',
      price: 4721.18,
      stop_loss: 4717.68,
      take_profit: 4777.18,
      position_size: 0.37,
      pnl: -85.47,
      risk_usd: 135.79,
      execution_source: 'signal_only',
      run_mode: 'LIVE',
      signal_action: 'exit',
      ai_reasoning: {
        decision: 'NO_GO',
        reason: '[MAS] Quant blocked: Score 0.44 below threshold 0.55. conf=0.44 | REJECT',
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

    expect(document.body.textContent).toContain('Exit Seen');
    expect(document.body.textContent).toContain('Position Impact Recorded');
    expect(document.body.textContent).toContain('Broker Execution [pass]');
    expect(document.body.textContent).toContain('Position close/update is recorded for this signal.');
    expect(document.body.textContent).toContain('Risk guard is not a blocking step for recorded exit/close updates.');
    expect(document.body.textContent).not.toContain('Broker Execution [skipped]');
  });
});
