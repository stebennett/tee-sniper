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

  // OneShotForm constrains the date input to [today, today+7]. Compute the
  // target relative to now so this test never drifts outside that window.
  const targetDate = new Date(Date.now() + 3 * 86400_000).toISOString().slice(0, 10);

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

    await userEvent.type(screen.getByLabelText(/target date/i), targetDate);
    await userEvent.clear(screen.getByLabelText(/^start$/i));
    await userEvent.type(screen.getByLabelText(/^start$/i), '14:00');
    await userEvent.clear(screen.getByLabelText(/^end$/i));
    await userEvent.type(screen.getByLabelText(/^end$/i), '16:00');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
    expect(received!.url).toContain('kind=one_shot');
    expect(received!.body.credentials).toBe('BLOB');
    expect(received!.body.target_date).toBe(targetDate);
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
