import { createContext, useCallback, useMemo, useState, type ReactNode } from 'react';

export interface AuthState {
  token: string | null;
  username: string | null;
  credentialsBlob: string | null;
  expiresAt: string | null;
}

export interface AuthContextValue extends AuthState {
  login: (token: string, username: string, credentialsBlob: string, expiresAt: string) => void;
  logout: () => void;
  setCredentialsBlob: (blob: string) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'tsa.token';
const USER_KEY = 'tsa.username';
const EXP_KEY = 'tsa.expiresAt';

function readInitial(): AuthState {
  if (typeof window === 'undefined') {
    return { token: null, username: null, credentialsBlob: null, expiresAt: null };
  }
  return {
    token: sessionStorage.getItem(TOKEN_KEY),
    username: sessionStorage.getItem(USER_KEY),
    expiresAt: sessionStorage.getItem(EXP_KEY),
    credentialsBlob: null,
  };
}

export function AuthProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: Partial<AuthState>;
}) {
  const [state, setState] = useState<AuthState>(() => ({ ...readInitial(), ...initial }));

  const login = useCallback(
    (token: string, username: string, credentialsBlob: string, expiresAt: string) => {
      sessionStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(USER_KEY, username);
      sessionStorage.setItem(EXP_KEY, expiresAt);
      setState({ token, username, credentialsBlob, expiresAt });
    },
    [],
  );

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(EXP_KEY);
    setState({ token: null, username: null, credentialsBlob: null, expiresAt: null });
  }, []);

  const setCredentialsBlob = useCallback((blob: string) => {
    setState((s) => ({ ...s, credentialsBlob: blob }));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, setCredentialsBlob }),
    [state, login, logout, setCredentialsBlob],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
