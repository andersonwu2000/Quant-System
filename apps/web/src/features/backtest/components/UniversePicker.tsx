import { useMemo, useState } from "react";
import { ListChecks } from "lucide-react";
import { Modal } from "@shared/ui";
import { useT } from "@core/i18n";
import { STOCK_LIST } from "../data/stocks";

interface UniversePickerProps {
  value: string[];
  onChange: (v: string[]) => void;
}

export function UniversePicker({ value, onChange }: UniversePickerProps) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const sorted = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? STOCK_LIST.filter(
          (s) =>
            s.ticker.toLowerCase().includes(q) ||
            s.name.toLowerCase().includes(q),
        )
      : STOCK_LIST;
    return [...filtered].sort((a, b) => {
      const aChecked = value.includes(a.ticker);
      const bChecked = value.includes(b.ticker);
      if (aChecked === bChecked) return a.ticker.localeCompare(b.ticker);
      return aChecked ? -1 : 1;
    });
  }, [query, value]);

  const toggle = (ticker: string) => {
    value.includes(ticker)
      ? onChange(value.filter((s) => s !== ticker))
      : onChange([...value, ticker]);
  };

  const handleClose = () => {
    setOpen(false);
    setQuery("");
  };

  return (
    <label className="space-y-1">
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {t.backtest.universe}
      </span>
      <div className="flex gap-2">
        <input
          value={value.join(",")}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((s) => s.trim().toUpperCase())
                .filter(Boolean),
            )
          }
          className="flex-1 bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="px-3 py-2 bg-slate-100 dark:bg-surface-light hover:bg-slate-200 dark:hover:bg-surface-light/80 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 transition-colors shrink-0"
        >
          <ListChecks size={16} />
        </button>
      </div>

      <Modal open={open} onClose={handleClose} title={t.backtest.universePickerTitle}>
        <div className="space-y-3">
          <input
            autoFocus
            placeholder={t.backtest.universeSearch}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {value.length} {t.backtest.universeSelected}
          </p>
          <div className="max-h-80 overflow-y-auto space-y-0.5 -mx-1 px-1">
            {sorted.map((stock) => {
              const checked = value.includes(stock.ticker);
              return (
                <label
                  key={stock.ticker}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                    checked
                      ? "bg-blue-50 dark:bg-blue-500/10"
                      : "hover:bg-slate-100 dark:hover:bg-surface-light"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(stock.ticker)}
                    className="accent-blue-500"
                  />
                  <span className="w-14 shrink-0 text-sm font-medium">
                    {stock.ticker}
                  </span>
                  <span className="text-sm text-slate-500 dark:text-slate-400 truncate">
                    {stock.name}
                  </span>
                </label>
              );
            })}
          </div>
          <div className="flex justify-end pt-1">
            <button
              onClick={handleClose}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {t.backtest.universeDone}
            </button>
          </div>
        </div>
      </Modal>
    </label>
  );
}
