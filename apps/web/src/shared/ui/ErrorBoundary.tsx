import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[#111111]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-8 max-w-lg">
            <h1 className="text-xl font-semibold text-red-400 mb-2">發生錯誤</h1>
            <p className="text-sm text-neutral-400 mb-4">{this.state.error.message}</p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload(); }}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              重新載入
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
