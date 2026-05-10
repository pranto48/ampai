/**
 * api-client.ts
 *
 * Provides a Tauri-aware fetch wrapper and convenience API client for AmpAI.
 *
 * ┌─ Browser (web app) ────────────────────────────────────────────────────────┐
 * │  All paths are used as-is (relative to the current origin).               │
 * └────────────────────────────────────────────────────────────────────────────┘
 * ┌─ Tauri desktop app ─────────────────────────────────────────────────────────┐
 * │  The Docker server URL stored in localStorage is prepended to every path.  │
 * │  e.g. "/api/chat"  →  "http://192.168.1.100:8001/api/chat"                 │
 * └────────────────────────────────────────────────────────────────────────────┘
 */

// ─── Constants ─────────────────────────────────────────────────────────────────

const SERVER_URL_KEY = 'ampai_server_url';

// ─── Environment detection ─────────────────────────────────────────────────────

/**
 * Returns `true` when the app is running inside the Tauri desktop shell.
 * Tauri injects `window.__TAURI__` at startup; its absence means we're in a
 * regular browser.
 */
export const isDesktopApp = (): boolean =>
  typeof window !== 'undefined' && '__TAURI__' in window;

/** @internal — same check, kept as a named alias for internal use. */
const isTauri = isDesktopApp;

// ─── Server URL helpers ────────────────────────────────────────────────────────

/**
 * Retrieves the Docker server base URL from localStorage
 * (e.g. `"http://192.168.1.100:8001"`), or `null` if not configured.
 */
export function getServerUrl(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(SERVER_URL_KEY);
}

/**
 * Persists the Docker server base URL to localStorage.
 * Trailing slashes are normalised away automatically.
 *
 * @param url  Full base URL including protocol and port,
 *             e.g. `"http://192.168.1.100:8001"`
 */
export function setServerUrl(url: string): void {
  localStorage.setItem(SERVER_URL_KEY, url.replace(/\/+$/, ''));
}

/**
 * Removes the stored Docker server URL from localStorage.
 * The next `isDesktopApp() && !getServerUrl()` check will prompt
 * the user to reconnect.
 */
export function clearServerUrl(): void {
  localStorage.removeItem(SERVER_URL_KEY);
}

// ─── Internal URL builder ──────────────────────────────────────────────────────

/**
 * Resolves the full request URL for the given API path.
 *
 * - In Tauri mode  → `<storedServerUrl><path>`
 * - In browser     → `<path>` unchanged (relative to current origin)
 */
function buildUrl(path: string): string {
  if (isTauri()) {
    const base = getServerUrl() ?? '';
    // Ensure exactly one slash between base and path
    const normalised = path.startsWith('/') ? path : `/${path}`;
    return `${base}${normalised}`;
  }
  return path;
}

// ─── Core request primitive ────────────────────────────────────────────────────

/**
 * Drop-in replacement for the global `fetch()` that automatically prepends
 * the configured server URL when running inside Tauri.
 *
 * @param path     API path, e.g. `"/api/chat"` or `"/healthz"`
 * @param options  Standard {@link RequestInit} options forwarded to `fetch`
 * @returns        A `Promise<Response>` just like `fetch()`
 *
 * @example
 * // In Tauri: fetches "http://192.168.1.100:8001/api/auth/login"
 * // In browser: fetches "/api/auth/login" (same-origin)
 * const res = await apiRequest('/api/auth/login', {
 *   method: 'POST',
 *   headers: { 'Content-Type': 'application/json' },
 *   body: JSON.stringify({ username, password }),
 * });
 */
export function apiRequest(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  return fetch(buildUrl(path), options);
}

// ─── Header helpers ────────────────────────────────────────────────────────────

function authHeaders(
  token?: string,
  extra: Record<string, string> = {}
): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// ─── High-level ApiClient ──────────────────────────────────────────────────────

/**
 * Convenience API client with typed HTTP methods.
 *
 * All methods respect the Tauri / browser URL-prefix behaviour via
 * {@link apiRequest}. Pass an optional Bearer `token` to include an
 * `Authorization` header automatically.
 *
 * @example
 * const res = await ApiClient.get('/api/auth/whoami', myToken);
 * const res = await ApiClient.post('/api/chat', { message: 'Hi' }, myToken);
 */
export const ApiClient = {
  /**
   * Performs a GET request.
   *
   * @param path   API path, e.g. `"/api/auth/whoami"`
   * @param token  Optional Bearer token for the Authorization header
   */
  get(path: string, token?: string): Promise<Response> {
    return apiRequest(path, {
      method: 'GET',
      headers: authHeaders(token),
    });
  },

  /**
   * Performs a POST request with a JSON-serialised body.
   *
   * @param path   API path, e.g. `"/api/chat"`
   * @param body   Request payload — will be stringified with `JSON.stringify`
   * @param token  Optional Bearer token for the Authorization header
   */
  post(path: string, body: unknown, token?: string): Promise<Response> {
    return apiRequest(path, {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
  },

  /**
   * Performs a PATCH request with a JSON-serialised body.
   *
   * @param path   API path, e.g. `"/api/admin/users/alice"`
   * @param body   Partial update payload — will be stringified with `JSON.stringify`
   * @param token  Optional Bearer token for the Authorization header
   */
  patch(path: string, body: unknown, token?: string): Promise<Response> {
    return apiRequest(path, {
      method: 'PATCH',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
  },

  /**
   * Performs a DELETE request.
   *
   * @param path   API path, e.g. `"/api/admin/users/alice"`
   * @param token  Optional Bearer token for the Authorization header
   */
  delete(path: string, token?: string): Promise<Response> {
    return apiRequest(path, {
      method: 'DELETE',
      headers: authHeaders(token),
    });
  },
} as const;
