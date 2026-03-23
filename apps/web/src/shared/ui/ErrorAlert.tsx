import { RefreshCw } from "lucide-react";
import { useT } from "@core/i18n";

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorAlert({ message, onRetry }: Props) {
  const { t } = useT();
  return (
    <div className="bg-red-500/10 text-red-400 rounded-xl p-4 text-sm flex items-center justify-between">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 transition-colors text-xs font-medium">
          <RefreshCw size={12} /> {t.common.retry}
        </button>
      )}
    </div>
  );
}
