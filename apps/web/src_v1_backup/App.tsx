import { Routes, Route, Navigate, useLocation, Link } from "react-router-dom";
import { lazy, Suspense, useState, useCallback, useMemo } from "react";
import { BookOpen, X } from "lucide-react";
import { Sidebar } from "@shared/layout";
import { ErrorBoundary, RouteErrorBoundary, ToastProvider, PageSkeleton } from "@shared/ui";
import { isAuthenticated, logout } from "@core/api";
import { I18nContext, getSavedLang, saveLang, translations, type Lang } from "@core/i18n";
import { ThemeProvider } from "@core/theme";
import { AuthProvider, useAuth } from "@core/auth";

const DashboardPage = lazy(() => import("@feat/dashboard").then(m => ({ default: m.DashboardPage })));
const TradingPage = lazy(() => import("@feat/trading").then(m => ({ default: m.TradingPage })));
const StrategiesPage = lazy(() => import("@feat/strategies").then(m => ({ default: m.StrategiesPage })));
const ResearchPage = lazy(() => import("@feat/alpha").then(m => ({ default: m.AlphaPage })));
const GuidePage = lazy(() => import("@feat/guide").then(m => ({ default: m.GuidePage })));
const RiskPage = lazy(() => import("@feat/risk").then(m => ({ default: m.RiskPage })));
const SettingsPage = lazy(() => import("@feat/settings").then(m => ({ default: m.SettingsPage })));
const AdminPage = lazy(() => import("@feat/admin").then(m => ({ default: m.AdminPage })));
const AutoAlphaPage = lazy(() => import("@feat/auto-alpha").then(m => ({ default: m.AutoAlphaPage })));
const NotFoundPage = lazy(() => import("@feat/not-found").then(m => ({ default: m.NotFoundPage })));

function RequireKey({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/settings" replace />;
  return <>{children}</>;
}

const GUIDE_SEEN_KEY = "quant-guide-seen";

function GuideHintBanner({ t }: { t: typeof translations["en"] }) {
  const [visible, setVisible] = useState(() => !localStorage.getItem(GUIDE_SEEN_KEY));

  const dismiss = useCallback(() => {
    localStorage.setItem(GUIDE_SEEN_KEY, "true");
    setVisible(false);
  }, []);

  if (!visible) return null;

  return (
    <div className="bg-blue-600 text-white text-sm flex items-center justify-between px-4 py-2">
      <div className="flex items-center gap-2">
        <BookOpen size={16} className="shrink-0" />
        <span>{t.settings.guideHint}</span>
        <Link
          to="/guide"
          onClick={dismiss}
          className="underline underline-offset-2 hover:text-blue-200 font-medium ml-1"
        >
          {t.nav.guide}
        </Link>
      </div>
      <button
        onClick={dismiss}
        className="p-1 hover:bg-blue-500 rounded transition-colors shrink-0"
        aria-label={t.common.close}
      >
        <X size={14} />
      </button>
    </div>
  );
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
      <GuideHintBanner t={i18nValue.t} />
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
              <Route path="/trading" element={<RequireKey><TradingPage /></RequireKey>} />
              <Route path="/strategies" element={<RequireKey><StrategiesPage /></RequireKey>} />
              <Route path="/research" element={<RequireKey><ResearchPage /></RequireKey>} />
              <Route path="/risk" element={<RequireKey><RiskPage /></RequireKey>} />
              <Route path="/guide" element={<GuidePage />} />
              <Route path="/auto-alpha" element={<RequireKey><AutoAlphaPage /></RequireKey>} />
              <Route path="/admin" element={<RequireKey><AdminPage /></RequireKey>} />
              {/* Legacy redirects */}
              <Route path="/portfolio" element={<Navigate to="/trading" replace />} />
              <Route path="/orders" element={<Navigate to="/trading" replace />} />
              <Route path="/paper-trading" element={<Navigate to="/trading" replace />} />
              <Route path="/backtest" element={<Navigate to="/research" replace />} />
              <Route path="/alpha" element={<Navigate to="/research" replace />} />
              <Route path="/allocation" element={<Navigate to="/research" replace />} />
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
