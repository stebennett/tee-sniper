import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../src/auth/AuthProvider';

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', initialAuth }: { route?: string; initialAuth?: Parameters<typeof AuthProvider>[0]['initial'] } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider initial={initialAuth}>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
