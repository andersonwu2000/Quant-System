import { useState, useRef, useEffect, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { useApi } from "@core/hooks";
import { isAuthenticated, login } from "@core/api";
import { useToast } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { langLabels, type Lang } from "@core/i18n";
import { useTheme, type Theme } from "@core/theme";
import { authEndpoints as authApi } from "@core/api";
import { translateApiError, isValidPassword } from "@core/utils";
import { systemApi } from "./api";
import { SystemMetrics } from "./components/SystemMetrics";

function CollapsibleSection({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl shadow-sm dark:shadow-none overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition-colors"
      >
        <span>{title}</span>
        <ChevronDown
          size={16}
          className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-slate-200 dark:border-surface-light pt-4">
          {children}
        </div>
      )}
    </div>
  );
}

export function SettingsPage({ onSave }: { onSave?: () => void } = {}) {
  const { t, lang, setLang } = useT();
  const { theme, setTheme } = useTheme();
  const { toast } = useToast();
  const { setRole } = useAuth();
  const { data: status, loading } = useApi(systemApi.status);
  const [loginMode, setLoginMode] = useState<"password" | "apikey">("password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // Change password state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [changePwLoading, setChangePwLoading] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const handleSave = async () => {
    setLoginError("");
    setLoginLoading(true);
    try {
      const credentials = loginMode === "apikey"
        ? { apiKey: key }
        : { username, password };
      const role = await login(credentials);
      setRole(role);
      setSaved(true);
      toast("success", t.toast.settingsSaved);
      onSave?.();
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setLoginError(translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setLoginLoading(false);
    }
  };

  const canSubmit = loginMode === "apikey" ? key.trim() : username.trim() && password.trim();

  const handleChangePassword = async () => {
    if (newPassword !== confirmNewPassword) {
      toast("error", t.admin.passwordMismatch);
      return;
    }
    setChangePwLoading(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      toast("success", t.settings.passwordChanged);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err) {
      toast("error", translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setChangePwLoading(false);
    }
  };

  const canChangePassword =
    currentPassword.trim() &&
    isValidPassword(newPassword) &&
    newPassword === confirmNewPassword;

  return (
    <div className="space-y-3">
      <h2 className="text-2xl font-bold mb-3">{t.settings.title}</h2>

      {!isAuthenticated() && (
        <div className="bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-xl p-4 text-sm">
          {t.settings.loginHint}
        </div>
      )}

      {/* 登入 */}
      <CollapsibleSection title={loginMode === "password" ? t.admin.loginWithPassword : t.settings.apiKey}>
        {loginMode === "password" ? (
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">{t.admin.usernameLabel}</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t.admin.usernameLabel}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">{t.admin.passwordLabel}</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t.admin.passwordHint}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
        ) : (
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={t.settings.apiKeyPlaceholder}
            className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        )}
        <div className="flex items-center justify-between pt-1">
          <button
            onClick={() => setLoginMode(loginMode === "password" ? "apikey" : "password")}
            className="text-xs text-blue-500 hover:text-blue-400 transition-colors"
          >
            {loginMode === "password" ? t.admin.loginWithApiKey : t.admin.loginWithPassword}
          </button>
          <button
            onClick={handleSave}
            disabled={loginLoading || !canSubmit}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {loginLoading ? "..." : saved ? t.settings.saved : t.settings.save}
          </button>
        </div>
        {loginError && (
          <p className="text-sm text-red-500 dark:text-red-400">{loginError}</p>
        )}
      </CollapsibleSection>

      {/* 修改密碼 */}
      {isAuthenticated() && (
        <CollapsibleSection title={t.settings.changePassword}>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">{t.settings.currentPassword}</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">{t.settings.newPassword}</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t.admin.passwordHint}
                className={`w-full bg-white dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                  newPassword && !isValidPassword(newPassword)
                    ? "border-red-400 dark:border-red-500"
                    : "border-slate-200 dark:border-surface-light"
                }`}
              />
              {newPassword && !isValidPassword(newPassword) && (
                <p className="mt-1 text-xs text-red-500">{t.admin.passwordHint}</p>
              )}
            </div>
            <div>
              <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">{t.settings.confirmNewPassword}</label>
              <input
                type="password"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                className={`w-full bg-white dark:bg-surface-dark border rounded-lg px-3 py-2 text-sm ${
                  confirmNewPassword && newPassword !== confirmNewPassword
                    ? "border-red-400 dark:border-red-500"
                    : "border-slate-200 dark:border-surface-light"
                }`}
              />
              {confirmNewPassword && newPassword !== confirmNewPassword && (
                <p className="mt-1 text-xs text-red-500">{t.admin.passwordMismatch}</p>
              )}
            </div>
          </div>
          <div className="flex justify-end pt-1">
            <button
              onClick={handleChangePassword}
              disabled={changePwLoading || !canChangePassword}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {changePwLoading ? "..." : t.settings.changePassword}
            </button>
          </div>
        </CollapsibleSection>
      )}

      {/* 語言 */}
      <CollapsibleSection title={t.settings.language}>
        <div className="flex gap-2">
          {(Object.entries(langLabels) as [Lang, string][]).map(([code, label]) => (
            <button
              key={code}
              onClick={() => setLang(code)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                lang === code
                  ? "bg-blue-500/20 text-blue-600 dark:text-blue-400"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-surface-dark"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </CollapsibleSection>

      {/* 主題 */}
      <CollapsibleSection title={t.settings.theme}>
        <div className="flex gap-2">
          {(["light", "dark", "system"] as Theme[]).map((option) => {
            const labels: Record<Theme, string> = {
              light: t.settings.themeLight,
              dark: t.settings.themeDark,
              system: t.settings.themeSystem,
            };
            return (
              <button
                key={option}
                onClick={() => setTheme(option)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  theme === option
                    ? "bg-blue-500/20 text-blue-600 dark:text-blue-400"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-surface-dark"
                }`}
              >
                {labels[option]}
              </button>
            );
          })}
        </div>
      </CollapsibleSection>

      {/* 系統狀態 */}
      <CollapsibleSection title={t.settings.systemStatus}>
        <SystemMetrics />
      </CollapsibleSection>
    </div>
  );
}
