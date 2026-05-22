import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedListPage } from './WantedListPage';
import type { WantedResponse } from '../api/types';

const fixtures: WantedResponse[] = [
  { id: '1', kind: 'one_shot', target_date: '2026-05-23',
    day_of_week: null, end_date: null,
    start_time: '14:00', end_time: '16:30', num_slots: 4, partners: [],
    has_credentials: true, notify: null, status: 'pending', attempts: [],
    created_at: '', updated_at: '' },
  { id: '2', kind: 'recurring', target_date: null, day_of_week: 0, end_date: null,
    start_time: '09:00', end_time: '11:00', num_slots: 2, partners: [],
    has_credentials: true, notify: null, status: 'disabled', attempts: [],
    created_at: '', updated_at: '' },
];

describe('WantedListPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('lists cards and filters by status', async () => {
    server.use(http.get(`${baseUrl}/api/wanted`, () => HttpResponse.json(fixtures)));
    renderWithProviders(<WantedListPage />, { initialAuth: { token: 'tok', username: 'alice' } });

    expect(await screen.findByText(/Sat\b.+May/)).toBeInTheDocument();
    expect(screen.getByText('Every Monday')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Disabled$/ }));
    expect(screen.queryByText(/Sat\b.+May/)).not.toBeInTheDocument();
    expect(screen.getByText('Every Monday')).toBeInTheDocument();
  });
});
