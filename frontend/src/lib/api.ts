import { browser } from '$app/environment';
import { PUBLIC_API_BASE_URL } from '$env/static/public';

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

const BASE = browser ? '' : PUBLIC_API_BASE_URL;

async function request<T>(
  method: string,
  path: string,
  body?: BodyInit | null,
  headers?: Record<string, string>,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      body: body ?? null,
      headers: { ...(headers ?? {}) },
    });
  } catch (e) {
    throw new ApiError(0, null, `Network error: ${(e as Error).message}`);
  }
  const text = await res.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }
  if (!res.ok) {
    const detail =
      parsed && typeof parsed === 'object' && 'detail' in parsed
        ? String((parsed as { detail: unknown }).detail)
        : '';
    const message = detail
      ? `${method} ${path} -> ${res.status}: ${detail}`
      : `${method} ${path} -> ${res.status}`;
    throw new ApiError(res.status, parsed, message);
  }
  return parsed as T;
}

export const api = {
  get: <T,>(path: string) => request<T>('GET', path),
  post: <T,>(path: string, body?: BodyInit | null) => request<T>('POST', path, body),
  postJson: <T,>(path: string, data: unknown) =>
    request<T>('POST', path, JSON.stringify(data), { 'Content-Type': 'application/json' }),
  postForm: <T,>(path: string, form: FormData) => request<T>('POST', path, form),
  putJson: <T,>(path: string, data: unknown) =>
    request<T>('PUT', path, JSON.stringify(data), { 'Content-Type': 'application/json' }),
  patchJson: <T,>(path: string, data: unknown) =>
    request<T>('PATCH', path, JSON.stringify(data), { 'Content-Type': 'application/json' }),
  del: <T,>(path: string) => request<T>('DELETE', path),
  sse: (path: string) => new EventSource(`${BASE}${path}`),
};
