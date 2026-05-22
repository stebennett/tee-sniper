import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const baseUrl = 'http://api.test';

// Default happy-path handlers. Individual tests override per-case.
export const handlers = [
  http.post(`${baseUrl}/api/encrypt-credentials`, async ({ request }) => {
    const body = (await request.json()) as { username: string; pin: string };
    return HttpResponse.json({ credentials: `enc(${body.username}:${body.pin})` });
  }),
  http.post(`${baseUrl}/api/login`, () =>
    HttpResponse.json({
      access_token: 'test-token',
      expires_at: new Date(Date.now() + 3600_000).toISOString(),
    }),
  ),
  http.get(`${baseUrl}/api/wanted`, () => HttpResponse.json([])),
  http.get(`${baseUrl}/api/partners`, () => HttpResponse.json({ partners: [] })),
];

export const server = setupServer(...handlers);
