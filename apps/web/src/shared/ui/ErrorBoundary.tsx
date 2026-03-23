import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 dark:bg-surface-dark flex items-center justify-center p-8">
          <div role="alert" className="bg-white dark:bg-surface rounded-xl p-8 max-w-md w-full text-center space-y-4 shadow-sm dark:shadow-none">
            <div className="text-red-500 dark:text-red-400 text-4xl">⚠</div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Something went wrong</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">{this.state.error?.message || "An unexpected error occurred"}</p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
