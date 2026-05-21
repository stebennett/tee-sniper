import { apiBaseUrl } from '../config';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  token?: string | null;
}

export async function request<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { token, body, headers, ...rest } = opts;
  const init: RequestInit = {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const resp = await fetch(`${apiBaseUrl()}${path}`, init);

  if (resp.status === 204) return undefined as T;

  const text = await resp.text();
  const data = text ? safeParse(text) : null;

  if (!resp.ok) {
    const detail = typeof data === 'object' && data && 'detail' in data
      ? String((data as { detail: unknown }).detail)
      : text || resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

function safeParse(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}
