import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiFetch } from './api';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiFetch', () => {
  it('uses JSON API detail as the error message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ detail: 'Reactivate this profile before enabling it for trading.' }),
      {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      },
    )));

    await expect(apiFetch('/api/broker-profiles/1/activate')).rejects.toThrow(
      'API Error (409): Reactivate this profile before enabling it for trading.',
    );
  });

  it('labels fetch rejections as network errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }));

    await expect(apiFetch('/api/broker-profiles/1/test')).rejects.toThrow(
      'Network error: Failed to fetch',
    );
  });
});
