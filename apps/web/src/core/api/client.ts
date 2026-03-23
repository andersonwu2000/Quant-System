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

export function isAuthenticated(): boolean {
  return localStorage.getItem(AUTH_STORAGE) === "true";
}

/** Login via backend JWT endpoint — sets httpOnly cookie automatically. Returns the user's role. */
export async function login(apiKey: string): Promise<UserRole> {
  const resp = await post<{ access_token: string }>("/api/v1/auth/login", { api_key: apiKey });
  localStorage.setItem(AUTH_STORAGE, "true");
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
}

// Initialize shared client with web adapter
initClient({
  getBaseUrl: () => "",  // web uses Vite proxy, paths are relative
  getHeaders: async () => {
    return { "Content-Type": "application/json" };
    // Auth is handled by httpOnly cookie (sent automatically by browser)
  },
});

// Initialize shared WS with browser location
initWs((channel: Channel) => {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/${channel}`;
});

// Re-export shared client functions
export { ApiError, get, post, put } from "@quant/shared";
