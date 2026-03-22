/**
 * Platform-agnostic HTTP client.
 *
 * Each platform (web / mobile) provides an adapter that resolves
 * base URL and auth headers. The generic get/post/put functions
 * work identically across platforms.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export interface ClientAdapter {
  getBaseUrl(): string;
  getHeaders(): Promise<Record<string, string>>;
}

let _adapter: ClientAdapter | null = null;

export function initClient(adapter: ClientAdapter) {
  _adapter = adapter;
}

function adapter(): ClientAdapter {
  if (!_adapter) throw new Error("Client not initialized — call initClient() first");
  return _adapter;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const a = adapter();
  const baseUrl = a.getBaseUrl();
  const headers = await a.getHeaders();

  const url = baseUrl ? `${baseUrl}${path}` : path;

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Network error");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const b = await res.json();
      detail = b.detail || detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

export const get = <T>(path: string) => request<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body);
export const put = <T>(path: string, body?: unknown) => request<T>("PUT", path, body);
