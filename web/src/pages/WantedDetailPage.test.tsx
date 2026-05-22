import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedDetailPage } from './WantedDetailPage';
import { Route, Routes } from 'react-router-dom';
import type { WantedResponse } from '../api/types';

const slot: WantedResponse = {
  id: 'abc', kind: 'one_shot', target_date: '2026-05-23',
  day_of_week: null, end_date: null,
  start_time: '14:00', end_time: '16:30', num_slots: 4, partners: [],
  has_credentials: true, notify: null, status: 'pending',
  attempts: [{ ts: '2026-05-19T10:00:00Z', target_date: '2026-05-23',
               outcome: 'no_slots', booking_id: null, error: null }],
  created_at: '', updated_at: '',
};

describe('WantedDetailPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('shows attempts and supports delete', async () => {
    server.use(
      http.get(`${baseUrl}/api/wanted/abc`, () => HttpResponse.json(slot)),
      http.delete(`${baseUrl}/api/wanted/abc`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    renderWithProviders(
      <Routes>
        <Route path="/wanted/:id" element={<WantedDetailPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/wanted/abc', initialAuth: { token: 'tok' } },
    );
    expect(await screen.findByText('no_slots')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /delete/i }));
    await userEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
  });

  it('has a back link to the list', async () => {
    server.use(http.get(`${baseUrl}/api/wanted/abc`, () => HttpResponse.json(slot)));
    renderWithProviders(
      <Routes>
        <Route path="/wanted/:id" element={<WantedDetailPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/wanted/abc', initialAuth: { token: 'tok' } },
    );
    await userEvent.click(await screen.findByRole('link', { name: /back to wanted/i }));
    expect(screen.getByText('LIST')).toBeInTheDocument();
  });

  it('edits partners and includes them in the save patch', async () => {
    let patchBody: { partners?: string[] } | null = null;
    server.use(
      http.get(`${baseUrl}/api/wanted/abc`, () => HttpResponse.json(slot)),
      http.get(`${baseUrl}/api/partners`, () =>
        HttpResponse.json({ partners: [
          { id: 'p1', name: 'Alice' },
          { id: 'p2', name: 'Bob' },
        ]}),
      ),
      http.patch(`${baseUrl}/api/wanted/abc`, async ({ request }) => {
        patchBody = (await request.json()) as { partners?: string[] };
        return HttpResponse.json({ ...slot, partners: patchBody.partners ?? [] });
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/wanted/:id" element={<WantedDetailPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/wanted/abc', initialAuth: { token: 'tok' } },
    );
    await userEvent.click(await screen.findByLabelText('Alice'));
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }));
    await waitFor(() => expect(patchBody).not.toBeNull());
    expect(patchBody!.partners).toEqual(['p1']);
  });
});
