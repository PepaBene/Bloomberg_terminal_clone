const BASE_URL = import.meta.env.VITE_API_URL ?? '';

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
    const url = new URL(`${BASE_URL}${path}`, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) url.searchParams.set(key, String(value));
      });
    }
    return url.toString();
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options;
    const url = this.buildUrl(path, params);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> ?? {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, { ...fetchOptions, headers });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(error.detail || 'Request failed', response.status);
    }

    return response.json();
  }

  get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: 'GET', params });
  }

  post<T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined, params });
  }

  // FastAPI's OAuth2PasswordRequestForm (used by POST /auth/token) expects
  // application/x-www-form-urlencoded, not JSON -- a plain post() call
  // would 422 against it.
  postForm<T>(path: string, form: Record<string, string>): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: new URLSearchParams(form).toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }

  // Server-Sent Events over a POST body (e.g. /v5/adviser/.../messages) --
  // `request()` above always awaits response.json(), which doesn't apply
  // to a streaming text/event-stream body, so this reads the raw stream
  // and yields one parsed {event, data} pair per SSE frame as they arrive.
  // Wire format is src/ai/streaming.py's format_sse(): "event: <name>\n"
  // followed by one or more "data: <line>\n" lines, frames separated by a
  // blank line.
  async *stream(path: string, body?: unknown): AsyncGenerator<{ event: string; data: unknown }> {
    const url = this.buildUrl(path);
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!response.ok || !response.body) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(error.detail || 'Request failed', response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let frameEnd: number;
      while ((frameEnd = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, frameEnd);
        buffer = buffer.slice(frameEnd + 2);
        const parsed = parseSSEFrame(frame);
        if (parsed) yield parsed;
      }
    }
  }
}

function parseSSEFrame(frame: string): { event: string; data: unknown } | null {
  let eventName = 'message';
  const dataLines: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''));
    }
  }
  if (dataLines.length === 0) return null;
  const raw = dataLines.join('\n');
  try {
    return { event: eventName, data: JSON.parse(raw) };
  } catch {
    return { event: eventName, data: raw };
  }
}

export class ApiError extends Error {
  constructor(public detail: string, public statusCode: number) {
    super(detail);
    this.name = 'ApiError';
  }
}

export const api = new ApiClient();
export default api;
