/**
 * Mobile platform adapter for @quant/shared client.
 * Stores credentials in Expo SecureStore and uses configurable base URL.
 */

import * as SecureStore from "expo-secure-store";
import { initClient, initWs } from "@quant/shared";
import type { Channel } from "@quant/shared";

const TOKEN_KEY = "jwt_token";
const API_KEY_KEY = "api_key";

let baseUrl = "http://localhost:8000";

export function setBaseUrl(url: string) {
  baseUrl = url.replace(/\/$/, "");

  // Re-initialize WS URL builder with new base URL
  initWs((channel: Channel) => {
    return baseUrl.replace(/^http/, "ws") + `/ws/${channel}`;
  });
}

export function getBaseUrl(): string {
  return baseUrl;
}

export async function saveToken(token: string) {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function clearToken() {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function saveApiKey(key: string) {
  await SecureStore.setItemAsync(API_KEY_KEY, key);
}

export async function getApiKey(): Promise<string | null> {
  return SecureStore.getItemAsync(API_KEY_KEY);
}

// Initialize shared client with mobile adapter
initClient({
  getBaseUrl: () => baseUrl,
  getHeaders: async () => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const token = await getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const apiKey = await getApiKey();
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    return headers;
  },
});

// Initialize WS URL builder with default base URL
initWs((channel: Channel) => {
  return baseUrl.replace(/^http/, "ws") + `/ws/${channel}`;
});

// Re-export shared client functions
export { ApiError, get, post, put } from "@quant/shared";
