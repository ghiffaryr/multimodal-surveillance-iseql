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

function resolveBase(): string {
  if (!browser) return PUBLIC_API_BASE_URL;
  return '';
}

const BASE = resolveBase() || PUBLIC_API_BASE_URL;

async function request<T>(
  method: string,
  path: string,
  body?: BodyInit | null | undefined,
  headers?: Record<string, string>
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    body: body ?? null,
    headers: { ...(headers ?? {}) },
  });
  const text = await res.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }
  if (!res.ok) {
    throw new ApiError(res.status, parsed, `${method} ${path} -> ${res.status}`);
  }
  return parsed as T;
}

export const api = {
  get: <T,>(path: string) => request<T>('GET', path),
  post: <T,>(path: string, body?: BodyInit | null) => request<T>('POST', path, body),
  postForm: <T,>(path: string, form: FormData) =>
    request<T>('POST', path, form),
  sse: (path: string) => new EventSource(`${BASE}${path}`),
};
