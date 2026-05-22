import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './AuthProvider';
import { ProtectedRoute } from './ProtectedRoute';

function setup(route: string, token: string | null) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider initial={{ token }}>
        <Routes>
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<div>SECRET</div>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  it('renders children when authed', () => {
    setup('/secret', 'tok');
    expect(screen.getByText('SECRET')).toBeInTheDocument();
  });
  it('redirects to /login when no token', () => {
    setup('/secret', null);
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
  });
});
