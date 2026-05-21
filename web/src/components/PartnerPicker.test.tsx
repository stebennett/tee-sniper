import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { PartnerPicker } from './PartnerPicker';
import { AuthProvider } from '../auth/AuthProvider';

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider initial={{ token: 'tok' }}>{ui}</AuthProvider>
    </QueryClientProvider>,
  );
}

describe('PartnerPicker', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('lists partners and toggles selection up to 3', async () => {
    server.use(http.get(`${baseUrl}/api/partners`, () =>
      HttpResponse.json({ partners: [
        { id: 'a', name: 'Alice' },
        { id: 'b', name: 'Bob' },
        { id: 'c', name: 'Carol' },
        { id: 'd', name: 'Dave' },
      ]}),
    ));
    const onChange = vi.fn();
    wrap(<PartnerPicker value={[]} onChange={onChange} />);
    expect(await screen.findByText('Alice')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Alice'));
    expect(onChange).toHaveBeenLastCalledWith(['a']);
  });

  it('disables remaining checkboxes once 3 selected', async () => {
    server.use(http.get(`${baseUrl}/api/partners`, () =>
      HttpResponse.json({ partners: [
        { id: 'a', name: 'A' }, { id: 'b', name: 'B' },
        { id: 'c', name: 'C' }, { id: 'd', name: 'D' },
      ]}),
    ));
    wrap(<PartnerPicker value={['a','b','c']} onChange={() => {}} />);
    expect((await screen.findByLabelText('D'))).toBeDisabled();
    expect(screen.getByLabelText('A')).not.toBeDisabled();
  });
});
