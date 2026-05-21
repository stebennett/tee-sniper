import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { LoginPage } from './LoginPage';
import { Route, Routes } from 'react-router-dom';

describe('LoginPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('logs in and navigates to /wanted', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/login' },
    );
    await userEvent.type(screen.getByLabelText(/username/i), 'alice');
    await userEvent.type(screen.getByLabelText(/pin/i), '1234');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
    expect(sessionStorage.getItem('tsa.token')).toBe('test-token');
  });

  it('shows "Invalid username or PIN" on 401', async () => {
    server.use(http.post(`${baseUrl}/api/login`, () =>
      HttpResponse.json({ detail: 'bad creds' }, { status: 401 }),
    ));
    renderWithProviders(<LoginPage />, { route: '/login' });
    await userEvent.type(screen.getByLabelText(/username/i), 'alice');
    await userEvent.type(screen.getByLabelText(/pin/i), 'x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByText(/Invalid username or PIN/i)).toBeInTheDocument();
  });
});
