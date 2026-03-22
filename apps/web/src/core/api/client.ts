/**
 * Web platform adapter for @quant/shared client.
 * Stores API key in localStorage and uses browser-relative URLs.
 */

import { initClient, initWs } from "@quant/shared";
import type { Channel } from "@quant/shared";

const API_KEY_STORAGE = "quant_api_key";

export function getApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) || "";
}

export function setApiKey(key: string) {
  localStorage.setItem(API_KEY_STORAGE, key);
}

export function clearApiKey() {
  localStorage.removeItem(API_KEY_STORAGE);
}

// Initialize shared client with web adapter
initClient({
  getBaseUrl: () => "",  // web uses Vite proxy, paths are relative
  getHeaders: async () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const apiKey = getApiKey();
    if (apiKey) headers["X-API-Key"] = apiKey;
    return headers;
  },
});

// Initialize shared WS with browser location
initWs((channel: Channel) => {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/${channel}`;
});

// Re-export shared client functions
export { ApiError, get, post, put } from "@quant/shared";
