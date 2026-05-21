import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server, baseUrl } from '../../test/handlers';
import { ApiError, request } from './client';

// Force apiBaseUrl() to return baseUrl during tests.
beforeAll(() => {
  window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl };
});

describe('request', () => {
  it('returns parsed JSON on 2xx', async () => {
    server.use(http.get(`${baseUrl}/ok`, () => HttpResponse.json({ hello: 'world' })));
    await expect(request<{ hello: string }>('/ok')).resolves.toEqual({ hello: 'world' });
  });

  it('throws ApiError with detail on non-2xx', async () => {
    server.use(
      http.get(`${baseUrl}/bad`, () =>
        HttpResponse.json({ detail: 'nope' }, { status: 422 }),
      ),
    );
    await expect(request('/bad')).rejects.toBeInstanceOf(ApiError);
    await expect(request('/bad')).rejects.toMatchObject({ status: 422, detail: 'nope' });
  });

  it('attaches Bearer token when provided', async () => {
    let seenAuth: string | null = null;
    server.use(
      http.get(`${baseUrl}/auth`, ({ request }) => {
        seenAuth = request.headers.get('authorization');
        return HttpResponse.json({});
      }),
    );
    await request('/auth', { token: 'abc' });
    expect(seenAuth).toBe('Bearer abc');
  });

  it('returns undefined for 204 No Content', async () => {
    server.use(http.delete(`${baseUrl}/x`, () => new HttpResponse(null, { status: 204 })));
    await expect(request('/x', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});
