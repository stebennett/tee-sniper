import { useMutation } from '@tanstack/react-query';
import { encryptCredentials, login } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';

export function useLogin() {
  const auth = useAuth();
  return useMutation({
    mutationFn: async (vars: { username: string; pin: string }) => {
      const { credentials } = await encryptCredentials(vars);
      const { access_token, expires_at } = await login({ credentials });
      auth.login(access_token, vars.username, credentials, expires_at);
      return { access_token };
    },
  });
}
