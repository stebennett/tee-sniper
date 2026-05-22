import { useQuery } from '@tanstack/react-query';
import { listPartners } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';

export function usePartners() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['partners'],
    queryFn: () => listPartners(token!).then((r) => r.partners),
    enabled: !!token,
    staleTime: 5 * 60_000,
  });
}
