import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useCallback, useMemo } from "react";
import { Sidebar } from "@shared/layout";
import { DashboardPage } from "@feat/dashboard";
import { PortfolioPage } from "@feat/portfolio";
import { StrategiesPage } from "@feat/strategies";
import { OrdersPage } from "@feat/orders";
import { BacktestPage } from "@feat/backtest";
import { RiskPage } from "@feat/risk";
import { SettingsPage } from "@feat/settings";
import { getApiKey } from "@core/api";
import { I18nContext, getSavedLang, saveLang, translations, type Lang } from "@core/i18n";

function RequireKey({ children }: { children: React.ReactNode }) {
  if (!getApiKey()) return <Navigate to="/settings" replace />;
  return <>{children}</>;
}

export default function App() {
  const [, refresh] = useState(0);
  const [lang, setLangState] = useState<Lang>(getSavedLang);

  const setLang = useCallback((l: Lang) => {
    saveLang(l);
    setLangState(l);
  }, []);

  const i18nValue = useMemo(() => ({
    t: translations[lang], lang, setLang,
  }), [lang, setLang]);

  return (
    <I18nContext.Provider value={i18nValue}>
      <div className="flex min-h-screen bg-surface-dark text-slate-100">
        <Sidebar />
        <main className="flex-1 p-6 overflow-auto">
          <Routes>
            <Route path="/settings" element={<SettingsPage onSave={() => refresh((n) => n + 1)} />} />
            <Route path="/" element={<RequireKey><DashboardPage /></RequireKey>} />
            <Route path="/portfolio" element={<RequireKey><PortfolioPage /></RequireKey>} />
            <Route path="/strategies" element={<RequireKey><StrategiesPage /></RequireKey>} />
            <Route path="/orders" element={<RequireKey><OrdersPage /></RequireKey>} />
            <Route path="/backtest" element={<RequireKey><BacktestPage /></RequireKey>} />
            <Route path="/risk" element={<RequireKey><RiskPage /></RequireKey>} />
          </Routes>
        </main>
      </div>
    </I18nContext.Provider>
  );
}
