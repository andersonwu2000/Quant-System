import { useState } from "react";
import { useApi } from "@core/hooks";
import { getApiKey, setApiKey } from "@core/api";
import { MetricCard } from "@shared/ui";
import { useT } from "@core/i18n";
import { langLabels, type Lang } from "@core/i18n";
import { systemApi } from "./api";

export function SettingsPage({ onSave }: { onSave?: () => void } = {}) {
  const { t, lang, setLang } = useT();
  const { data: status, loading } = useApi(systemApi.status);
  const [key, setKey] = useState(getApiKey());
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setApiKey(key);
    setSaved(true);
    onSave?.();
    setTimeout(() => setSaved(false), 2000);
  };

  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{t.settings.title}</h2>

      {!getApiKey() && (
        <div className="bg-amber-500/10 text-amber-400 rounded-xl p-4 text-sm">
          {t.settings.apiKeyHint} <code className="bg-surface-dark px-1.5 py-0.5 rounded">dev-key</code>
        </div>
      )}

      <div className="bg-surface rounded-xl p-5 space-y-4">
        <p className="text-sm font-medium text-slate-400">{t.settings.apiKey}</p>
        <div className="flex gap-3">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={t.settings.apiKeyPlaceholder}
            className="flex-1 bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm"
          />
          <button onClick={handleSave}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
            {saved ? t.settings.saved : t.settings.save}
          </button>
        </div>
      </div>

      <div className="bg-surface rounded-xl p-5 space-y-4">
        <p className="text-sm font-medium text-slate-400">{t.settings.language}</p>
        <div className="flex gap-2">
          {(Object.entries(langLabels) as [Lang, string][]).map(([code, label]) => (
            <button
              key={code}
              onClick={() => setLang(code)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                lang === code
                  ? "bg-blue-500/20 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-surface-dark"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-slate-400">{t.dashboard.loading}</div>}
      {status && (
        <div>
          <p className="text-sm font-medium text-slate-400 mb-3">{t.settings.systemStatus}</p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label={t.settings.mode} value={status.mode} />
            <MetricCard label={t.settings.uptime} value={fmtUptime(status.uptime_seconds)} />
            <MetricCard label={t.settings.strategiesRunning} value={String(status.strategies_running)} />
            <MetricCard label={t.settings.dataSource} value={status.data_source} />
          </div>
        </div>
      )}
    </div>
  );
}
