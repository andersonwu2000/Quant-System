import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  labels?: {
    title?: string;
    fallbackMessage?: string;
    action?: string;
  };
}

interface State {
  hasError: boolean;
  error: Error | null;
}

abstract class BaseErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`${this.constructor.name} caught:`, error, info.componentStack);
  }

  protected get title() { return this.props.labels?.title ?? "Something went wrong"; }
  protected get message() { return this.state.error?.message || (this.props.labels?.fallbackMessage ?? "An unexpected error occurred"); }
  protected get action() { return this.props.labels?.action ?? "Reload"; }
}

export class ErrorBoundary extends BaseErrorBoundary {
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 dark:bg-surface-dark flex items-center justify-center p-8">
          <div role="alert" className="bg-white dark:bg-surface rounded-xl p-8 max-w-md w-full text-center space-y-4 shadow-sm dark:shadow-none">
            <div className="text-red-500 dark:text-red-400 text-4xl">⚠</div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{this.title}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">{this.message}</p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {this.action}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Inline error boundary for per-route use — renders within the layout, preserving sidebar. */
export class RouteErrorBoundary extends BaseErrorBoundary {
  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="bg-white dark:bg-surface rounded-xl p-8 max-w-md mx-auto mt-12 text-center space-y-4 shadow-sm dark:shadow-none">
          <div className="text-red-500 dark:text-red-400 text-4xl">⚠</div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{this.title}</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400">{this.message}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {this.props.labels?.action ?? "Retry"}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
