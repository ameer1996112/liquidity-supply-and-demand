import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

import { RiskRulesPanel } from '../RiskRulesPanel';

describe('RiskRulesPanel', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('loads symbol rules from backend api', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          rules: [
            {
              symbol: 'EURUSD',
              max_lot_size: 2,
              min_lot_size: 0.01,
              lot_step: 0.01,
              risk_percent: 0.5,
              pip_size: 0.0001,
              pip_value_per_lot: 10,
              stop_loss_buffer_pips: 1,
              max_positions: 3,
              enabled: true,
            },
          ],
          count: 1,
        }),
      })
    );

    await act(async () => {
      root.render(<RiskRulesPanel />);
    });

    expect(container.textContent).toContain('EURUSD');
    expect(container.textContent).toContain('Backend calculates final position size');
  });

  it('saves edited symbol rules to backend api', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ rules: [], count: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ rule: { symbol: 'XAUUSD' } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ rules: [], count: 0 }),
      });

    vi.stubGlobal('fetch', fetchMock);

    await act(async () => {
      root.render(<RiskRulesPanel />);
    });

    const addButton = container.querySelector('button');
    expect(addButton).not.toBeNull();

    await act(async () => {
      addButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    const symbolInput = container.querySelector('input[aria-label="Symbol"]') as HTMLInputElement;
    expect(symbolInput).not.toBeNull();

    const valueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    )?.set;
    valueSetter?.call(symbolInput, 'XAUUSD');

    await act(async () => {
      symbolInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const saveButton = container.querySelector('button[aria-label="Save rule"]');
    expect(saveButton).not.toBeNull();

    await act(async () => {
      saveButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/rules/symbols',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });
});
