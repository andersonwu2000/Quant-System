import { Link } from "react-router-dom";

interface EmptyStateProps {
  message: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}

export function EmptyState({ message, actionLabel, actionHref, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <p className="text-slate-500 dark:text-slate-400 text-sm">{message}</p>
      {actionLabel && actionHref && (
        <Link
          to={actionHref}
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        >
          {actionLabel}
        </Link>
      )}
      {actionLabel && onAction && !actionHref && (
        <button
          onClick={onAction}
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
