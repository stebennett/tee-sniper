import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { AuthProvider } from './AuthProvider';
import { useAuth } from './useAuth';

function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="token">{a.token ?? 'none'}</span>
      <span data-testid="user">{a.username ?? 'none'}</span>
      <button onClick={() => a.login('tok', 'alice', 'BLOB',
                                     new Date('2099-01-01').toISOString())}>L</button>
      <button onClick={() => a.logout()}>O</button>
    </div>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => sessionStorage.clear());

  it('starts logged out', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('token').textContent).toBe('none');
  });

  it('login() persists token + username to sessionStorage', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    expect(screen.getByTestId('token').textContent).toBe('tok');
    expect(screen.getByTestId('user').textContent).toBe('alice');
    expect(sessionStorage.getItem('tsa.token')).toBe('tok');
    expect(sessionStorage.getItem('tsa.username')).toBe('alice');
  });

  it('logout() clears state and sessionStorage', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    act(() => { screen.getByText('O').click(); });
    expect(screen.getByTestId('token').textContent).toBe('none');
    expect(sessionStorage.getItem('tsa.token')).toBeNull();
  });

  it('rehydrates token from sessionStorage', () => {
    sessionStorage.setItem('tsa.token', 'persisted');
    sessionStorage.setItem('tsa.username', 'bob');
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('token').textContent).toBe('persisted');
  });

  it('does not persist credentialsBlob across reload', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    expect(sessionStorage.getItem('tsa.credentialsBlob')).toBeNull();
  });
});
