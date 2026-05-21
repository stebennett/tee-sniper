import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createWanted, deleteWanted, getWanted, listWanted, patchWanted,
} from '../api/endpoints';
import type {
  CreateOneShotRequest, CreateRecurringRequest, PatchWantedRequest, WantedKind,
} from '../api/types';
import { useAuth } from '../auth/useAuth';

export function useWantedList() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['wanted'],
    queryFn: () => listWanted(token!),
    enabled: !!token,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useWanted(id: string) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['wanted', id],
    queryFn: () => getWanted(token!, id),
    enabled: !!token,
  });
}

export function useCreateWanted() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      kind: WantedKind;
      body: CreateOneShotRequest | CreateRecurringRequest;
    }) => createWanted(token!, vars.kind, vars.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wanted'] }),
  });
}

export function usePatchWanted(id: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PatchWantedRequest) => patchWanted(token!, id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wanted'] });
      qc.invalidateQueries({ queryKey: ['wanted', id] });
    },
  });
}

export function useDeleteWanted() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWanted(token!, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wanted'] }),
  });
}
