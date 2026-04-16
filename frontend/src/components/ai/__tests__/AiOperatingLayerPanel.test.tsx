/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { AiOperatingLayerPanel } from '../AiOperatingLayerPanel';

describe('AiOperatingLayerPanel', () => {
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

  test('renders verdict, health badge, and degraded reason', () => {
    act(() => {
      root.render(
        <AiOperatingLayerPanel
          run={{
            analysisMode: 'posttrade_review',
            layeredOutput: {
              topLevel: { verdict: 'weak setup', confidence: 42 },
            },
            moduleStatus: {
              chartContext: {
                status: 'degraded',
                reason: 'TradingView MCP unavailable',
              },
            },
            chartContext: {
              status: 'degraded',
              reason: 'TradingView MCP unavailable',
              structured: {
                setupEvidence: {
                  status: 'degraded',
                  focusZone: null,
                  focusImage: null,
                  reason: 'setup image unavailable',
                },
                zones: [],
                pineLabels: [],
              },
            },
            pineContext: {},
          }}
        />
      );
    });

    expect(container.textContent).toContain('weak setup');
    expect(container.textContent).toContain('Chart Context');
    expect(container.textContent).toContain('TradingView MCP unavailable');
    expect(container.textContent).toContain('Setup Evidence');
  });
});
