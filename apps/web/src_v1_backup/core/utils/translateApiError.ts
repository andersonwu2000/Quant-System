import type { Translations } from "@core/i18n/locales/en";

/**
 * Maps known backend error messages to i18n strings.
 * Falls back to the original message if no match is found.
 */
export function translateApiError(message: string, t: Translations): string {
  const e = t.errors;
  const m = message.toLowerCase();

  if (m === "invalid credentials") return e.invalidCredentials;
  if (m.includes("account locked")) return e.accountLocked;
  if (m === "invalid api key") return e.invalidApiKey;
  if (m === "missing authorization token") return e.missingToken;
  if (m === "invalid or expired token") return e.invalidToken;
  if (m === "account disabled or deleted") return e.accountDisabled;
  if (m === "token has been revoked") return e.tokenRevoked;
  if (m === "current password is incorrect") return e.wrongCurrentPassword;
  if (m.includes("already exists")) return e.usernameExists;
  if (m === "user not found") return e.userNotFound;
  if (m === "cannot downgrade your own role") return e.cannotDowngradeOwnRole;
  if (m === "cannot deactivate your own account") return e.cannotDeactivateSelf;
  if (m === "cannot delete your own account") return e.cannotDeleteSelf;
  if (m === "cannot delete the last active admin") return e.cannotDeleteLastAdmin;
  if (m === "api key users cannot change password") return e.apiKeyCannotChangePassword;
  if (m.includes("username+password or api_key")) return e.missingCredentials;
  if (m === "network error") return e.networkError;
  if (m.includes("too many concurrent backtests")) return e.tooManyBacktests;
  if (m.includes("backtest task not found")) return e.backtestNotFound;
  if (m.includes("strategy") && m.includes("not found")) return e.strategyNotFound;
  if (m.includes("rule") && m.includes("not found")) return e.ruleNotFound;

  return message;
}
