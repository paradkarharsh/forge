import type { ApiEnvelope, ApiErrorDetail, ApiErrorEnvelope } from './types';

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(status: number, error: ApiErrorDetail) {
    super(error.message || `API error ${error.code} (${status})`);
    this.name = 'ApiClientError';
    this.code = error.code;
    this.status = status;
    this.details = error.details;
    this.requestId = error.request_id;
  }
}

export interface RequestOptions extends RequestInit {
  readonly params?: Record<string, string | number | boolean | null | undefined>;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = (
      baseUrl ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000'
    ).replace(/\/+$/, '');
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  private buildUrl(
    path: string,
    params?: Record<string, string | number | boolean | null | undefined>
  ): string {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const url = new URL(`${this.baseUrl}${cleanPath}`);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, headers, ...rest } = options;
    const url = this.buildUrl(path, params);

    const mergedHeaders: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(headers as Record<string, string>),
    };

    let response: Response;
    try {
      response = await fetch(url, {
        ...rest,
        headers: mergedHeaders,
        credentials: 'include',
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw err;
      }
      throw new ApiClientError(0, {
        code: 'network_error',
        message:
          err instanceof Error ? err.message : 'Network connection failure',
      });
    }

    let payload: unknown = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
    }

    if (!response.ok) {
      const errorPayload = payload as ApiErrorEnvelope | null;
      if (errorPayload && errorPayload.error) {
        throw new ApiClientError(response.status, errorPayload.error);
      }
      throw new ApiClientError(response.status, {
        code: `http_${response.status}`,
        message: response.statusText || `HTTP request failed (${response.status})`,
      });
    }

    // Unpack Forge API envelope: { data: T, error: null }
    const envelope = payload as ApiEnvelope<T>;
    if (envelope && 'data' in envelope) {
      return envelope.data;
    }

    return payload as T;
  }

  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean | null | undefined>,
    signal?: AbortSignal
  ): Promise<T> {
    return this.request<T>(path, { method: 'GET', params, signal });
  }

  async post<T, B = unknown>(
    path: string,
    body?: B,
    signal?: AbortSignal
  ): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });
  }

  async patch<T, B = unknown>(
    path: string,
    body?: B,
    signal?: AbortSignal
  ): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });
  }

  async delete<T>(path: string, signal?: AbortSignal): Promise<T> {
    return this.request<T>(path, { method: 'DELETE', signal });
  }
}

export const apiClient = new ApiClient();
