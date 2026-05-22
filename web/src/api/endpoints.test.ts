import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server, baseUrl } from '../../test/handlers';
import * as api from './endpoints';

beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

describe('endpoints', () => {
  it('encryptCredentials posts plaintext', async () => {
    const result = await api.encryptCredentials({ username: 'u', pin: 'p' });
    expect(result.credentials).toBe('enc(u:p)');
  });

  it('login posts the blob', async () => {
    const result = await api.login({ credentials: 'BLOB' });
    expect(result.access_token).toBe('test-token');
  });

  it('listWanted sends the bearer token', async () => {
    let auth: string | null = null;
    server.use(
      http.get(`${baseUrl}/api/wanted`, ({ request }) => {
        auth = request.headers.get('authorization');
        return HttpResponse.json([]);
      }),
    );
    await api.listWanted('tok');
    expect(auth).toBe('Bearer tok');
  });

  it('createWanted appends ?kind=', async () => {
    let url: string | null = null;
    server.use(
      http.post(`${baseUrl}/api/wanted`, ({ request }) => {
        url = request.url;
        return HttpResponse.json({ id: 'x' }, { status: 201 });
      }),
    );
    await api.createWanted('tok', 'one_shot', {
      target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
      num_slots: 2, partners: [], credentials: 'BLOB',
    });
    expect(url).toContain('kind=one_shot');
  });
});
