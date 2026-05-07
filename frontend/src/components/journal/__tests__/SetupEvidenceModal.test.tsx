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
            focus_zone: { id: 18429, label: 'SUPPLY A+', low: 1.3541, high: 1.3561, source: 'signal' },
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(container.textContent).toContain('SUPPLY A+');
    expect(container.textContent).toContain('18429');
    expect(container.querySelector('button[aria-label="Close setup evidence"]')).not.toBeNull();
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

    const button = container.querySelector('button[aria-label="Close setup evidence"]');
    act(() => {
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    root.unmount();
  });

  test('calls onClose from escape key and backdrop click', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const onClose = vi.fn();

    act(() => {
      root.render(
        <SetupEvidenceModal
          open
          onClose={onClose}
          evidence={{
            status: 'ok',
            focus_zone: { label: 'SUPPLY A+' },
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });

    const dialog = container.querySelector('[role="dialog"]');
    act(() => {
      dialog?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    });

    expect(onClose).toHaveBeenCalledTimes(2);
    root.unmount();
  });
});
