/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { SetupEvidencePanel } from '../SetupEvidencePanel';

describe('SetupEvidencePanel', () => {
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

  test('renders focused setup image and primary zone context', () => {
    act(() => {
      root.render(
        <SetupEvidencePanel
          evidence={{
            status: 'ok',
            focusZone: {
              label: 'Institutional Liquidity Protocol [Pro]',
              high: 0.721,
              low: 0.7195,
            },
            focusImage: { url: 'https://provider/setup.png' },
            reason: '',
          }}
          zones={[
            {
              label: 'Institutional Liquidity Protocol [Pro]',
              high: 0.721,
              low: 0.7195,
            },
          ]}
          pineLabels={[{ label: 'LONG\nE: 0.7200', price: 0.72 }]}
        />
      );
    });

    const image = container.querySelector('img[alt="Focused setup"]');
    expect(image?.getAttribute('src')).toBe('https://provider/setup.png');
    expect(container.textContent).toContain('0.7195 - 0.7210');
    expect(container.textContent).toContain('LONG');
  });

  test('renders degraded reason without image', () => {
    act(() => {
      root.render(
        <SetupEvidencePanel
          evidence={{
            status: 'degraded',
            focusZone: null,
            focusImage: null,
            reason: 'setup image unavailable',
          }}
          zones={[]}
          pineLabels={[]}
        />
      );
    });

    expect(container.textContent).toContain('setup image unavailable');
    expect(container.textContent).toContain('No focus zone detected');
  });
});
