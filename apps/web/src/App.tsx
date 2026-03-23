import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { lazy, Suspense, useState, useCallback, useMemo } from "react";
import { Sidebar } from "@shared/layout";
import { ErrorBoundary, RouteErrorBoundary, ToastProvider, PageSkeleton } from "@shared/ui";
import { isAuthenticated, logout } from "@core/api";
import { I18nContext, getSavedLang, saveLang, translations, type Lang } from "@core/i18n";
import { ThemeProvider } from "@core/theme";
import { AuthProvider, useAuth } from "@core/auth";

const DashboardPage = lazy(() => import("@feat/dashboard").then(m => ({ default: m.DashboardPage })));
const PortfolioPage = lazy(() => import("@feat/portfolio").then(m => ({ default: m.PortfolioPage })));
const StrategiesPage = lazy(() => import("@feat/strategies").then(m => ({ default: m.StrategiesPage })));
const OrdersPage = lazy(() => import("@feat/orders").then(m => ({ default: m.OrdersPage })));
const BacktestPage = lazy(() => import("@feat/backtest").then(m => ({ default: m.BacktestPage })));
const RiskPage = lazy(() => import("@feat/risk").then(m => ({ default: m.RiskPage })));
const SettingsPage = lazy(() => import("@feat/settings").then(m => ({ default: m.SettingsPage })));
const AdminPage = lazy(() => import("@feat/admin").then(m => ({ default: m.AdminPage })));
const NotFoundPage = lazy(() => import("@feat/not-found").then(m => ({ default: m.NotFoundPage })));

function RequireKey({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/settings" replace />;
  return <>{children}</>;
}

function AppContent() {
  const [, refresh] = useState(0);
  const [lang, setLangState] = useState<Lang>(getSavedLang);
  const { clearRole } = useAuth();
  const location = useLocation();

  const setLang = useCallback((l: Lang) => {
    saveLang(l);
    setLangState(l);
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    clearRole();
    refresh((n) => n + 1);
  }, [clearRole]);

  const i18nValue = useMemo(() => ({
    t: translations[lang], lang, setLang,
  }), [lang, setLang]);

  return (
    <I18nContext.Provider value={i18nValue}>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg focus:text-sm focus:font-medium">
        {i18nValue.t.common.skipToContent}
      </a>
      <div className="flex min-h-screen bg-slate-200 dark:bg-surface-dark text-slate-900 dark:text-slate-100">
        <Sidebar onLogout={isAuthenticated() ? handleLogout : undefined} />
        <main id="main-content" className="flex-1 overflow-auto">
          <Suspense fallback={<div className="p-6"><PageSkeleton /></div>}>
            <RouteErrorBoundary key={location.pathname} labels={{
              title: i18nValue.t.common.errorTitle,
              fallbackMessage: i18nValue.t.common.unexpectedError,
              action: i18nValue.t.common.retry,
            }}>
            <div className="p-6 page-enter">
            <Routes>
              <Route path="/settings" element={<SettingsPage onSave={() => refresh((n) => n + 1)} />} />
              <Route path="/" element={<RequireKey><DashboardPage /></RequireKey>} />
              <Route path="/portfolio" element={<RequireKey><PortfolioPage /></RequireKey>} />
              <Route path="/strategies" element={<RequireKey><StrategiesPage /></RequireKey>} />
              <Route path="/orders" element={<RequireKey><OrdersPage /></RequireKey>} />
              <Route path="/backtest" element={<RequireKey><BacktestPage /></RequireKey>} />
              <Route path="/risk" element={<RequireKey><RiskPage /></RequireKey>} />
              <Route path="/admin" element={<RequireKey><AdminPage /></RequireKey>} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </div>
            </RouteErrorBoundary>
          </Suspense>
        </main>
      </div>
    </I18nContext.Provider>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ThemeProvider>
          <AuthProvider>
            <AppContent />
          </AuthProvider>
        </ThemeProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
