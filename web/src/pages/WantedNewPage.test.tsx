import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedNewPage } from './WantedNewPage';
import { Route, Routes } from 'react-router-dom';

describe('WantedNewPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('submits a one-shot wanted slot and navigates back to /wanted', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let received: { url: string; body: any } | null = null;
    server.use(http.post(`${baseUrl}/api/wanted`, async ({ request }) => {
      received = { url: request.url, body: await request.json() };
      return HttpResponse.json({ id: 'new' }, { status: 201 });
    }));

    renderWithProviders(
      <Routes>
        <Route path="/wanted/new" element={<WantedNewPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      {
        route: '/wanted/new',
        initialAuth: { token: 'tok', credentialsBlob: 'BLOB' },
      },
    );

    await userEvent.type(screen.getByLabelText(/target date/i), '2026-05-25');
    await userEvent.clear(screen.getByLabelText(/^start$/i));
    await userEvent.type(screen.getByLabelText(/^start$/i), '14:00');
    await userEvent.clear(screen.getByLabelText(/^end$/i));
    await userEvent.type(screen.getByLabelText(/^end$/i), '16:00');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
    expect(received!.url).toContain('kind=one_shot');
    expect(received!.body.credentials).toBe('BLOB');
    expect(received!.body.target_date).toBe('2026-05-25');
  });

  it('toggles to Recurring mode', async () => {
    renderWithProviders(<WantedNewPage />, {
      route: '/wanted/new',
      initialAuth: { token: 'tok', credentialsBlob: 'BLOB' },
    });
    await userEvent.click(screen.getByRole('tab', { name: /recurring/i }));
    expect(screen.getByLabelText(/day of week/i)).toBeInTheDocument();
  });
});
