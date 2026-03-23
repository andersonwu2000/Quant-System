import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from "react";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
  exiting?: boolean;
}

interface ToastOptions {
  duration?: number;
}

interface ToastContextValue {
  toast: (type: ToastType, message: string, options?: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue>({
  toast: () => {},
});

const MAX_VISIBLE = 5;
const DEFAULT_DURATION = 4000;

const icons: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const styles: Record<ToastType, string> = {
  success: "border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  error: "border-red-300 dark:border-red-500/40 bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300",
  warning: "border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300",
  info: "border-blue-300 dark:border-blue-500/40 bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300",
};

const iconColors: Record<ToastType, string> = {
  success: "text-emerald-400",
  error: "text-red-400",
  warning: "text-amber-400",
  info: "text-blue-400",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    // Mark as exiting for animation
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
    // Remove after animation
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 200);
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (type: ToastType, message: string, options?: ToastOptions) => {
      const id = nextId.current++;
      const duration = options?.duration ?? DEFAULT_DURATION;

      setToasts((prev) => {
        const next = [...prev, { id, type, message }];
        // If exceeding max, remove oldest
        if (next.length > MAX_VISIBLE) {
          const removed = next.splice(0, next.length - MAX_VISIBLE);
          removed.forEach((t) => {
            const timer = timers.current.get(t.id);
            if (timer) {
              clearTimeout(timer);
              timers.current.delete(t.id);
            }
          });
        }
        return next;
      });

      const timer = setTimeout(() => {
        dismiss(id);
      }, duration);
      timers.current.set(id, timer);
    },
    [dismiss],
  );

  // Cleanup all timers on unmount
  useEffect(() => {
    const t = timers.current;
    return () => {
      t.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const contextValue: ToastContextValue = { toast };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
        role="status"
        aria-live="polite"
      >
        {toasts.map((t) => {
          const Icon = icons[t.type];
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-center gap-3 border rounded-lg px-4 py-3 shadow-lg backdrop-blur-sm min-w-[280px] max-w-[400px] transition-all duration-200 ${
                t.exiting
                  ? "opacity-0 translate-x-4"
                  : "opacity-100 translate-x-0 animate-slide-in-right"
              } ${styles[t.type]}`}
            >
              <Icon size={18} className={`flex-shrink-0 ${iconColors[t.type]}`} />
              <span className="flex-1 text-sm">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                className="flex-shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
                aria-label="Close"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
