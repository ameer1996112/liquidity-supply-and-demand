/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test, vi } from 'vitest';
import { SetupEvidenceModal } from '../SetupEvidenceModal';

describe('SetupEvidenceModal', () => {
  test('renders the focused setup image and zone header when open', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceModal
          open
          onClose={() => {}}
          evidence={{
            status: 'ok',
            focus_zone: { label: 'SUPPLY A+', price: 1.3541 },
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(container.textContent).toContain('SUPPLY A+');
    expect(
      container.querySelector('img[alt="Focused setup evidence"]')?.getAttribute('src')
    ).toBe('https://provider/setup.png');
    root.unmount();
  });

  test('calls onClose when the close button is clicked', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const onClose = vi.fn();

    act(() => {
      root.render(
        <SetupEvidenceModal
          open
          onClose={onClose}
          evidence={{
            status: 'degraded',
            focus_zone: { label: 'SUPPLY A+' },
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    const button = container.querySelector('button');
    act(() => {
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    root.unmount();
  });
});
