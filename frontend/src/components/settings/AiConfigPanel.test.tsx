/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AiConfigPanel } from './AiConfigPanel';

vi.mock('@/lib/api', () => ({
  fetchAiConfig: vi.fn().mockResolvedValue({
    ai: {
      ai_filter_enabled: true,
      ai_provider: 'anthropic',
      ai_model: 'model',
      ai_base_url: '',
      ai_min_confidence: 75,
      ai_timeout_seconds: 5,
      ai_api_key_set: true,
    },
    ml: { ml_guardian_enabled: true, ml_min_confidence: 0.6 },
    ensemble: {
      enable_llm_filter: true,
      run_shadow_mode: true,
      ai_mode: 'shadow',
    },
    execution: {
      trading_kill_switch: false,
      run_mode: 'PAPER',
      execution_mode: 'paper',
      live_trading_enabled: false,
      live_shadow: true,
      meta_api_configured: false,
      meta_api_region: '',
    },
    risk: {
      trinity_enabled: true,
      trinity_max_daily_loss_pct: 4,
      trinity_max_drawdown_pct: 8,
      trinity_max_risk_per_trade_pct: 1,
      trinity_max_positions: 3,
      risk_percent: 0.5,
    },
  }),
  fetchGraduationStatus: vi.fn().mockResolvedValue({
    ready: false,
    reason: 'Need more data',
    metrics: {
      sample_size: 0,
      edge_pct: 0,
      sample_size_ai_blocked: 0,
      sample_size_ai_allowed: 0,
    },
    thresholds: {
      min_sample_size: 30,
      min_edge_pct: 5,
    },
  }),
  fetchAiOperatingLayerConfig: vi.fn().mockResolvedValue({
    panic_mode: false,
    modules: {
      chart_context: 'inherit',
      debate_review: 'enabled',
    },
    provider: {
      enabled: false,
      base_url: 'http://localhost:8765',
      timeout_seconds: 1,
      retry_count: 2,
    },
  }),
  patchAiOperatingLayerConfig: vi.fn().mockResolvedValue({
    panic_mode: true,
    modules: {
      chart_context: 'enabled',
      debate_review: 'disabled',
    },
    provider: {
      enabled: true,
      base_url: 'http://provider.test',
      timeout_seconds: 2,
      retry_count: 3,
    },
  }),
  fetchAiModeToggles: vi.fn().mockResolvedValue({ toggles: [] }),
  fetchKillSwitchLog: vi.fn().mockResolvedValue({ events: [] }),
  setAiMode: vi.fn().mockResolvedValue({}),
}));

describe('AiConfigPanel AI Operating Layer controls', () => {
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
    vi.clearAllMocks();
  });

  it('loads and saves the AI operating layer config', async () => {
    const api = await import('@/lib/api');

    await act(async () => {
      root.render(<AiConfigPanel />);
    });

    expect(container.textContent).toContain('AI Operating Layer');
    expect(container.textContent).toContain('Panic Mode');
    expect(container.textContent).toContain('Provider Endpoint');
    expect(container.textContent).toContain('Retry Count');

    const selects = container.querySelectorAll('select');
    expect(selects.length).toBeGreaterThan(0);

    await act(async () => {
      const panicButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent?.includes('OFF')
      );
      panicButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));

      const firstSelect = selects[0] as HTMLSelectElement;
      firstSelect.value = 'enabled';
      firstSelect.dispatchEvent(new Event('change', { bubbles: true }));

      const endpointInput = container.querySelector(
        'input[data-testid="ai-operating-layer-provider-endpoint"]'
      ) as HTMLInputElement | null;
      if (endpointInput) {
        endpointInput.value = 'http://provider.test';
        endpointInput.dispatchEvent(new Event('input', { bubbles: true }));
        endpointInput.dispatchEvent(new Event('change', { bubbles: true }));
      }

      const saveButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent?.includes('Save')
      );
      saveButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(api.patchAiOperatingLayerConfig).toHaveBeenCalledWith({
      panic_mode: true,
      modules: {
        chart_context: 'enabled',
        debate_review: 'enabled',
      },
      provider: {
        enabled: false,
        base_url: 'http://localhost:8765',
        timeout_seconds: 1,
        retry_count: 2,
      },
    });
  });

  it('shows broker-profile MetaAPI execution status when UI-managed accounts are active', async () => {
    const api = await import('@/lib/api');
    vi.mocked(api.fetchAiConfig).mockResolvedValueOnce({
      ai: {
        ai_filter_enabled: true,
        ai_provider: 'anthropic',
        ai_model: 'model',
        ai_base_url: '',
        ai_min_confidence: 75,
        ai_timeout_seconds: 5,
        ai_api_key_set: true,
      },
      ml: { ml_guardian_enabled: true, ml_min_confidence: 0.6 },
      ensemble: {
        enable_llm_filter: true,
        run_shadow_mode: true,
        ai_mode: 'shadow',
      },
      execution: {
        trading_kill_switch: false,
        run_mode: 'LIVE',
        execution_mode: 'METAAPI',
        live_trading_enabled: true,
        live_shadow: false,
        meta_api_configured: false,
        meta_api_region: 'london',
        broker_profiles_configured: true,
        active_broker_profiles: 2,
      },
      risk: {
        trinity_enabled: true,
        trinity_max_daily_loss_pct: 4,
        trinity_max_drawdown_pct: 8,
        trinity_max_risk_per_trade_pct: 1,
        trinity_max_positions: 3,
        risk_percent: 0.5,
      },
    });

    await act(async () => {
      root.render(<AiConfigPanel />);
    });

    expect(container.textContent).toContain('Broker Profiles');
    expect(container.textContent).toContain('2 active');
    expect(container.textContent).not.toContain('Not configured');
  });
});
