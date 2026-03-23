import { createContext, useContext, useState, useCallback, useEffect, createElement } from "react";
import type { ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import {
  saveApiKey,
  saveToken,
  clearToken,
  setBaseUrl,
  getApiKey,
  getToken,
} from "../api/client";
import { system, auth } from "@quant/shared";

// TODO: Extract user role from JWT token after login (decode JWT payload to get
// role field) and expose it in AuthState so mobile UI can enforce role-based access.
export interface AuthState {
  authenticated: boolean;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (serverUrl: string, apiKey: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const SAVED_URL_KEY = "server_url";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    loading: true,
    error: null,
  });

  const login = useCallback(
    async (serverUrl: string, apiKey: string) => {
      setState({ authenticated: false, loading: true, error: null });
      try {
        setBaseUrl(serverUrl);
        await SecureStore.setItemAsync(SAVED_URL_KEY, serverUrl);
        await saveApiKey(apiKey);
        const { access_token } = await auth.login(apiKey);
        await saveToken(access_token);
        setState({ authenticated: true, loading: false, error: null });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Connection failed";
        setState({ authenticated: false, loading: false, error: message });
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    await clearToken();
    await SecureStore.deleteItemAsync("api_key");
    setState({ authenticated: false, loading: false, error: null });
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    (async () => {
      // Restore saved base URL first (C3)
      const savedUrl = await SecureStore.getItemAsync(SAVED_URL_KEY);
      if (savedUrl) {
        setBaseUrl(savedUrl);
      }

      const apiKey = await getApiKey();
      if (apiKey) {
        try {
          await system.health();
          setState({ authenticated: true, loading: false, error: null });
        } catch {
          setState({ authenticated: false, loading: false, error: null });
        }
      } else {
        setState({ authenticated: false, loading: false, error: null });
      }
    })();
  }, []);

  return createElement(AuthContext.Provider, { value: { ...state, login, logout } }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
