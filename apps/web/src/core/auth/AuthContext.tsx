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
    localStorage.setItem(ROLE_STORAGE_KEY, r);
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
    const payload = JSON.parse(atob(parts[1]));
    const role = payload.role;
    if (typeof role === "string" && role in ROLE_HIERARCHY) return role as UserRole;
    return "viewer";
  } catch {
    return "viewer";
  }
}
