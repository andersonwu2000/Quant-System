import { Lock } from "lucide-react";

interface Props {
  title: string;
  description: string;
  requires: string;
}

export function TradingModePlaceholder({ title, description, requires }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 space-y-4 text-center">
      <div className="w-14 h-14 rounded-full bg-slate-100 dark:bg-surface-light flex items-center justify-center">
        <Lock size={24} className="text-slate-400" />
      </div>
      <div className="space-y-1">
        <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">{description}</p>
      </div>
      <p className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-4 py-2 rounded-lg">
        {requires}
      </p>
    </div>
  );
}
