import { Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense, useState, useCallback, useMemo } from "react";
import { Sidebar } from "@shared/layout";
import { ErrorBoundary } from "@shared/ui";
import { isAuthenticated, logout } from "@core/api";
import { I18nContext, getSavedLang, saveLang, translations, type Lang } from "@core/i18n";

const DashboardPage = lazy(() => import("@feat/dashboard").then(m => ({ default: m.DashboardPage })));
const PortfolioPage = lazy(() => import("@feat/portfolio").then(m => ({ default: m.PortfolioPage })));
const StrategiesPage = lazy(() => import("@feat/strategies").then(m => ({ default: m.StrategiesPage })));
const OrdersPage = lazy(() => import("@feat/orders").then(m => ({ default: m.OrdersPage })));
const BacktestPage = lazy(() => import("@feat/backtest").then(m => ({ default: m.BacktestPage })));
const RiskPage = lazy(() => import("@feat/risk").then(m => ({ default: m.RiskPage })));
const SettingsPage = lazy(() => import("@feat/settings").then(m => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import("@feat/not-found").then(m => ({ default: m.NotFoundPage })));

function RequireKey({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/settings" replace />;
  return <>{children}</>;
}

export default function App() {
  const [, refresh] = useState(0);
  const [lang, setLangState] = useState<Lang>(getSavedLang);

  const setLang = useCallback((l: Lang) => {
    saveLang(l);
    setLangState(l);
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    refresh((n) => n + 1);
  }, []);

  const i18nValue = useMemo(() => ({
    t: translations[lang], lang, setLang,
  }), [lang, setLang]);

  return (
    <ErrorBoundary>
      <I18nContext.Provider value={i18nValue}>
        <div className="flex min-h-screen bg-surface-dark text-slate-100">
          <Sidebar onLogout={isAuthenticated() ? handleLogout : undefined} />
          <main className="flex-1 p-6 overflow-auto">
            <Suspense fallback={<div className="text-slate-400 p-6">Loading...</div>}>
              <Routes>
                <Route path="/settings" element={<SettingsPage onSave={() => refresh((n) => n + 1)} />} />
                <Route path="/" element={<RequireKey><DashboardPage /></RequireKey>} />
                <Route path="/portfolio" element={<RequireKey><PortfolioPage /></RequireKey>} />
                <Route path="/strategies" element={<RequireKey><StrategiesPage /></RequireKey>} />
                <Route path="/orders" element={<RequireKey><OrdersPage /></RequireKey>} />
                <Route path="/backtest" element={<RequireKey><BacktestPage /></RequireKey>} />
                <Route path="/risk" element={<RequireKey><RiskPage /></RequireKey>} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </I18nContext.Provider>
    </ErrorBoundary>
  );
}
