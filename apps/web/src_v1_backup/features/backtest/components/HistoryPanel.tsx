import { useState } from "react";
import { Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { fmtPct, fmtNum, fmtDate } from "@core/utils";
import { useT } from "@core/i18n";
import type { BacktestHistoryEntry } from "../hooks/useBacktestHistory";

interface Props {
  history: BacktestHistoryEntry[];
  onSelect: (entry: BacktestHistoryEntry) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  selectedIds: Set<string>;
  onToggleCompare: (id: string) => void;
}

export function HistoryPanel({ history, onSelect, onRemove, onClear, selectedIds, onToggleCompare }: Props) {
  const { t } = useT();
  const [expanded, setExpanded] = useState(true);

  if (history.length === 0) return null;

  return (
    <div className="bg-surface rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors"
      >
        <span>{t.backtest.history} ({history.length})</span>
        <div className="flex items-center gap-2">
          <span
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            className="text-xs text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
          >
            {t.backtest.clearAll}
          </span>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-surface-light">
          {history.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-3 px-5 py-2.5 border-b border-surface-light/50 hover:bg-surface-light/30 transition-colors"
            >
              <input
                type="checkbox"
                checked={selectedIds.has(entry.id)}
                onChange={() => onToggleCompare(entry.id)}
                className="accent-blue-500"
                title={t.backtest.selectForComparison}
              />
              <button
                onClick={() => onSelect(entry)}
                className="flex-1 text-left text-sm"
              >
                <span className="font-medium">{entry.result.strategy_name}</span>
                <span className="text-slate-500 ml-2">{fmtDate(entry.timestamp)}</span>
                <span className={`ml-3 ${entry.result.total_return >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {fmtPct(entry.result.total_return)}
                </span>
                <span className="text-slate-500 ml-2">SR {fmtNum(entry.result.sharpe)}</span>
              </button>
              <button
                onClick={() => onRemove(entry.id)}
                className="text-slate-500 hover:text-red-400 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
