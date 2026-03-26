import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import { Sidebar } from '../shared/layout/Sidebar';
import { Skeleton } from '../shared/ui/Skeleton';
import { ErrorBoundary } from '../shared/ui/ErrorBoundary';

const OverviewPage = lazy(() => import('../pages/OverviewPage'));
const StrategyPage = lazy(() => import('../pages/StrategyPage'));
const RiskPage = lazy(() => import('../pages/RiskPage'));
const BacktestPage = lazy(() => import('../pages/BacktestPage'));
const SettingsPage = lazy(() => import('../pages/SettingsPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 2 },
  },
});

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div className="flex min-h-screen bg-[#111111]">
            <Sidebar />
            <main className="flex-1 overflow-auto">
              <div className="mx-auto max-w-7xl p-6">
                <Suspense fallback={<Skeleton className="h-96" />}>
                  <Routes>
                    <Route path="/" element={<OverviewPage />} />
                    <Route path="/strategy" element={<StrategyPage />} />
                    <Route path="/risk" element={<RiskPage />} />
                    <Route path="/backtest" element={<BacktestPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Suspense>
              </div>
            </main>
          </div>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
