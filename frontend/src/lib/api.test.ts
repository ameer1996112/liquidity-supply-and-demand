import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiFetch, resolveApiBaseUrl } from './api';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiFetch', () => {
  it('uses the same-origin backend proxy for Railway browser deployments', () => {
    expect(resolveApiBaseUrl(
      'https://grand-learning-production-bc96.up.railway.app',
      'https://frontend-production-a7cf.up.railway.app',
    )).toBe('/backend');
  });

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
