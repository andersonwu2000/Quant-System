import { useState, useRef, useEffect } from "react";
import { useApi } from "@core/hooks";
import { isAuthenticated, login } from "@core/api";
import { MetricCard, MetricCardSkeleton, useToast } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { langLabels, type Lang } from "@core/i18n";
import { useTheme, type Theme } from "@core/theme";
import { systemApi } from "./api";
import { SystemMetrics } from "./components/SystemMetrics";

export function SettingsPage({ onSave }: { onSave?: () => void } = {}) {
  const { t, lang, setLang } = useT();
  const { theme, setTheme } = useTheme();
  const { toast } = useToast();
  const { setRole } = useAuth();
  const { data: status, loading } = useApi(systemApi.status);
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const handleSave = async () => {
    setLoginError("");
    setLoginLoading(true);
    try {
      const role = await login(key);
      setRole(role);
      setSaved(true);
      toast("success", t.toast.settingsSaved);
      onSave?.();
      timerRef.current = setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoginLoading(false);
    }
  };

  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{t.settings.title}</h2>

      {!isAuthenticated() && (
        <div className="bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-xl p-4 text-sm">
          {t.settings.apiKeyHint} <code className="bg-slate-100 dark:bg-surface-dark px-1.5 py-0.5 rounded">dev-key</code>
        </div>
      )}

      <div className="bg-white dark:bg-surface rounded-xl p-5 space-y-4 shadow-sm dark:shadow-none">
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">{t.settings.apiKey}</p>
        <div className="flex gap-3">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={t.settings.apiKeyPlaceholder}
            className="flex-1 bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
          <button
            onClick={handleSave}
            disabled={loginLoading || !key.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {loginLoading ? "..." : saved ? t.settings.saved : t.settings.save}
          </button>
        </div>
        {loginError && (
          <p className="text-sm text-red-500 dark:text-red-400">{loginError}</p>
        )}
      </div>

      <div className="bg-white dark:bg-surface rounded-xl p-5 space-y-4 shadow-sm dark:shadow-none">
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">{t.settings.language}</p>
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
      </div>

      <div className="bg-white dark:bg-surface rounded-xl p-5 space-y-4 shadow-sm dark:shadow-none">
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">{t.settings.theme}</p>
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
      </div>

      {loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton />
        </div>
      )}
      {status && (
        <div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-3">{t.settings.systemStatus}</p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label={t.settings.mode} value={status.mode} />
            <MetricCard label={t.settings.uptime} value={fmtUptime(status.uptime_seconds)} />
            <MetricCard label={t.settings.strategiesRunning} value={String(status.strategies_running)} />
            <MetricCard label={t.settings.dataSource} value={status.data_source} />
          </div>
        </div>
      )}

      <SystemMetrics />
    </div>
  );
}
