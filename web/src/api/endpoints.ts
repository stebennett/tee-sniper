import { request } from './client';
import type {
  CreateOneShotRequest,
  CreateRecurringRequest,
  EncryptRequest,
  EncryptResponse,
  LoginRequest,
  LoginResponse,
  PartnerListResponse,
  PatchWantedRequest,
  WantedKind,
  WantedResponse,
} from './types';

export function encryptCredentials(body: EncryptRequest): Promise<EncryptResponse> {
  return request('/api/encrypt-credentials', { method: 'POST', body });
}

export function login(body: LoginRequest): Promise<LoginResponse> {
  return request('/api/login', { method: 'POST', body });
}

export function listWanted(token: string): Promise<WantedResponse[]> {
  return request('/api/wanted', { token });
}

export function getWanted(token: string, id: string): Promise<WantedResponse> {
  return request(`/api/wanted/${id}`, { token });
}

export function createWanted(
  token: string,
  kind: WantedKind,
  body: CreateOneShotRequest | CreateRecurringRequest,
): Promise<WantedResponse> {
  return request(`/api/wanted?kind=${kind}`, { method: 'POST', body, token });
}

export function patchWanted(
  token: string,
  id: string,
  body: PatchWantedRequest,
): Promise<WantedResponse> {
  return request(`/api/wanted/${id}`, { method: 'PATCH', body, token });
}

export function deleteWanted(token: string, id: string): Promise<void> {
  return request(`/api/wanted/${id}`, { method: 'DELETE', token });
}

export function listPartners(token: string): Promise<PartnerListResponse> {
  return request('/api/partners', { token });
}
