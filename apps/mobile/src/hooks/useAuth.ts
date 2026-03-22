import { useState, useCallback } from "react";
import {
  saveApiKey,
  saveToken,
  clearToken,
  setBaseUrl,
  getApiKey,
  getToken,
} from "../api/client";
import { system } from "../api/endpoints";

export interface AuthState {
  authenticated: boolean;
  loading: boolean;
  error: string | null;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    loading: false,
    error: null,
  });

  const login = useCallback(
    async (serverUrl: string, apiKey: string) => {
      setState({ authenticated: false, loading: true, error: null });
      try {
        setBaseUrl(serverUrl);
        await saveApiKey(apiKey);
        // Verify connection by calling health check
        await system.health();
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
    setState({ authenticated: false, loading: false, error: null });
  }, []);

  const checkSession = useCallback(async () => {
    const apiKey = await getApiKey();
    if (apiKey) {
      try {
        await system.health();
        setState({ authenticated: true, loading: false, error: null });
      } catch {
        setState({ authenticated: false, loading: false, error: null });
      }
    }
  }, []);

  return { ...state, login, logout, checkSession };
}
