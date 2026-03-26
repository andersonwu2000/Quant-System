/**
 * Web platform adapter for @quant/shared client.
 * Uses httpOnly cookie for auth (set by /auth/login).
 * Falls back to API key in localStorage for backward compatibility.
 */

import { initClient, initWs, post } from "@quant/shared";
import type { Channel } from "@quant/shared";
import type { UserRole } from "@quant/shared";
import { extractRoleFromJwt } from "@core/auth";

const AUTH_STORAGE = "quant_authenticated";
const TOKEN_STORAGE = "quant_access_token";

export function isAuthenticated(): boolean {
  return localStorage.getItem(AUTH_STORAGE) === "true";
}

/** Login via backend JWT endpoint — sets httpOnly cookie automatically. Returns the user's role. */
export async function login(credentials: { username: string; password: string } | { apiKey: string }): Promise<UserRole> {
  const body = "apiKey" in credentials
    ? { api_key: credentials.apiKey }
    : { username: credentials.username, password: credentials.password };
  const resp = await post<{ access_token: string }>("/api/v1/auth/login", body);
  localStorage.setItem(AUTH_STORAGE, "true");
  localStorage.setItem(TOKEN_STORAGE, resp.access_token);
  return extractRoleFromJwt(resp.access_token);
}

/** Logout — clears cookie and local flag. */
export async function logout(): Promise<void> {
  try {
    await post("/api/v1/auth/logout", {});
  } catch {
    // best effort
  }
  localStorage.removeItem(AUTH_STORAGE);
  localStorage.removeItem(TOKEN_STORAGE);
}

/** Get the stored access token for WebSocket auth. */
export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE);
}

// Initialize shared client with web adapter
initClient({
  getBaseUrl: () => "",  // web uses Vite proxy, paths are relative
  getHeaders: async () => {
    return { "Content-Type": "application/json" };
    // Auth is handled by httpOnly cookie (sent automatically by browser)
  },
});

// Initialize shared WS with browser location + auth token
initWs((channel: Channel) => {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const token = localStorage.getItem(TOKEN_STORAGE);
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}//${location.host}/ws/${channel}${tokenParam}`;
});

// Re-export shared client functions
export { ApiError, get, post, put, del } from "@quant/shared";
