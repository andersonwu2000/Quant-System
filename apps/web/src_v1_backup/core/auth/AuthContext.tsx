import { createContext, useContext, useState, useCallback, useMemo } from "react";
import type { UserRole } from "@quant/shared";

const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 0,
  researcher: 1,
  trader: 2,
  risk_manager: 3,
  admin: 4,
};

const ROLE_STORAGE_KEY = "quant_user_role";

export interface AuthContextValue {
  role: UserRole;
  hasRole: (minRole: UserRole) => boolean;
  setRole: (role: UserRole) => void;
  clearRole: () => void;
}

function getSavedRole(): UserRole {
  // If the auth flag is gone (e.g. JWT cookie expired and user logged out),
  // clear the stale role to avoid privilege desync.
  if (localStorage.getItem("quant_authenticated") !== "true") {
    localStorage.removeItem(ROLE_STORAGE_KEY);
    return "viewer";
  }

  // Prefer role derived from the JWT token (tamper-resistant).
  const token = localStorage.getItem("quant_api_key");
  if (token) {
    const jwtRole = extractRoleFromJwt(token);
    // If the token is a real JWT with an embedded role, use it.
    // Fall back to localStorage only for non-JWT API keys (where
    // extractRoleFromJwt returns the default "viewer").
    if (jwtRole !== "viewer") return jwtRole;
  }

  // Fallback: localStorage role (for plain API-key auth or legacy tokens).
  const stored = localStorage.getItem(ROLE_STORAGE_KEY);
  if (stored && stored in ROLE_HIERARCHY) return stored as UserRole;
  return "viewer";
}

const AuthContext = createContext<AuthContextValue>({
  role: "viewer",
  hasRole: () => false,
  setRole: () => {},
  clearRole: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<UserRole>(getSavedRole);

  const setRole = useCallback((r: UserRole) => {
    // Role is derived from the JWT token at init; only update runtime state.
    // localStorage write kept as fallback for non-JWT (plain API key) auth.
    const token = localStorage.getItem("quant_api_key");
    const jwtRole = token ? extractRoleFromJwt(token) : "viewer";
    if (jwtRole === "viewer") {
      // Non-JWT API key — persist to localStorage as before.
      localStorage.setItem(ROLE_STORAGE_KEY, r);
    }
    setRoleState(r);
  }, []);

  const clearRole = useCallback(() => {
    localStorage.removeItem(ROLE_STORAGE_KEY);
    setRoleState("viewer");
  }, []);

  const hasRole = useCallback(
    (minRole: UserRole) => ROLE_HIERARCHY[role] >= ROLE_HIERARCHY[minRole],
    [role],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ role, hasRole, setRole, clearRole }),
    [role, hasRole, setRole, clearRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

/**
 * Extract role from a JWT access_token (base64-decode the payload).
 * Returns "viewer" if decoding fails or role is missing.
 */
export function extractRoleFromJwt(token: string): UserRole {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return "viewer";
    // JWT uses base64url encoding: replace URL-safe chars and add padding
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    const role = payload.role;
    if (typeof role === "string" && role in ROLE_HIERARCHY) return role as UserRole;
    return "viewer";
  } catch {
    return "viewer";
  }
}
