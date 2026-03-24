import { useMemo, useState } from "react";
import { ListChecks, Check, X } from "lucide-react";
import { useT } from "@core/i18n";
import { STOCK_LIST, PRESETS, type StockEntry } from "../data/stocks";

interface UniversePickerProps {
  value: string[];
  onChange: (v: string[]) => void;
}

type MarketTab = "US" | "TW" | "ETF";

export function UniversePicker({ value, onChange }: UniversePickerProps) {
  const { t, lang } = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [marketTab, setMarketTab] = useState<MarketTab>("US");

  const filtered = useMemo(() => {
    let list = STOCK_LIST.filter((s) => s.market === marketTab);
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (s) =>
          s.ticker.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q) ||
          (s.sector ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [query, marketTab]);

  const grouped = useMemo(() => {
    const map = new Map<string, StockEntry[]>();
    for (const s of filtered) {
      const key = s.sector ?? "Other";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(s);
    }
    return map;
  }, [filtered]);

  const toggle = (ticker: string) => {
    value.includes(ticker)
      ? onChange(value.filter((s) => s !== ticker))
      : onChange([...value, ticker]);
  };

  const selectFiltered = () => {
    const tickers = filtered.map((s) => s.ticker);
    onChange([...new Set([...value, ...tickers])]);
  };

  const deselectFiltered = () => {
    const tickers = new Set(filtered.map((s) => s.ticker));
    onChange(value.filter((v) => !tickers.has(v)));
  };

  const checkedInView = filtered.filter((s) => value.includes(s.ticker)).length;

  const visiblePresets = PRESETS.filter(
    (p) => p.key.startsWith(marketTab.toLowerCase()),
  );

  const tabCounts: Record<MarketTab, number> = {
    US: STOCK_LIST.filter((s) => s.market === "US").length,
    TW: STOCK_LIST.filter((s) => s.market === "TW").length,
    ETF: STOCK_LIST.filter((s) => s.market === "ETF").length,
  };

  const tabLabels: Record<MarketTab, [string, string]> = {
    US: ["美股", "US"],
    TW: ["台股", "TW"],
    ETF: ["ETF", "ETF"],
  };

  return (
    <label className="space-y-1">
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {t.backtest.universe}
      </span>
      {/* Trigger area */}
      <div className="flex gap-2">
        <div
          onClick={() => setOpen(true)}
          className="flex-1 bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm cursor-pointer hover:border-blue-400 dark:hover:border-blue-500 transition-colors min-h-[38px] flex items-center gap-1 flex-wrap"
        >
          {value.length === 0 ? (
            <span className="text-slate-400">{t.backtest.universeSearch}</span>
          ) : value.length <= 6 ? (
            value.map((v) => (
              <span
                key={v}
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 rounded text-xs font-medium"
              >
                {v}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); toggle(v); }}
                  className="hover:text-red-500"
                ><X size={10} /></button>
              </span>
            ))
          ) : (
            <span className="text-slate-600 dark:text-slate-300">
              {value.length} {t.backtest.universeSelected}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="px-3 py-2 bg-slate-100 dark:bg-surface-light hover:bg-slate-200 dark:hover:bg-surface-light/80 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 transition-colors shrink-0"
        >
          <ListChecks size={16} />
        </button>
      </div>

      {/* Fullscreen-ish modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 pt-16" onClick={() => { setOpen(false); setQuery(""); }}>
          <div
            className="bg-white dark:bg-[#1e293b] rounded-t-xl sm:rounded-xl shadow-2xl w-full max-w-2xl sm:mx-4 max-h-[80vh] sm:max-h-[75vh] flex flex-col sm:mt-8"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-5 pb-3">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                {t.backtest.universePickerTitle}
              </h3>
              <button
                onClick={() => { setOpen(false); setQuery(""); }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              ><X size={18} /></button>
            </div>

            {/* Tabs + presets + search (fixed) */}
            <div className="px-5 pb-3 space-y-2.5 border-b border-slate-100 dark:border-slate-700">
              {/* Market tabs */}
              <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg">
                {(["US", "TW", "ETF"] as MarketTab[]).map((tab) => {
                  const [zh, en] = tabLabels[tab];
                  return (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => { setMarketTab(tab); setQuery(""); }}
                      className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        marketTab === tab
                          ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm"
                          : "text-slate-500 dark:text-slate-400"
                      }`}
                    >
                      {lang === "zh" ? zh : en}
                      <span className="ml-1 text-slate-400 dark:text-slate-500">({tabCounts[tab]})</span>
                    </button>
                  );
                })}
              </div>

              {/* Presets for current tab */}
              {visiblePresets.length > 0 && (
                <div className="flex gap-1.5 flex-wrap">
                  {visiblePresets.map((p) => (
                    <button
                      key={p.key}
                      type="button"
                      onClick={() => onChange(p.tickers)}
                      className="px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-blue-50 dark:hover:bg-blue-500/10 hover:border-blue-300 dark:hover:border-blue-500/40 transition-colors"
                    >
                      {lang === "zh" ? p.labelZh : p.label}
                    </button>
                  ))}
                </div>
              )}

              {/* Search + bulk actions */}
              <div className="flex gap-2 items-center">
                <input
                  autoFocus
                  placeholder={t.backtest.universeSearch}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-1.5 text-sm"
                />
                <button type="button" onClick={selectFiltered}
                  className="px-2 py-1 text-[11px] font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded transition-colors whitespace-nowrap"
                ><Check size={11} className="inline mr-0.5" />{lang === "zh" ? "全選" : "All"}</button>
                <button type="button" onClick={deselectFiltered}
                  className="px-2 py-1 text-[11px] font-medium text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded transition-colors whitespace-nowrap"
                ><X size={11} className="inline mr-0.5" />{lang === "zh" ? "清除" : "Clear"}</button>
              </div>

              <p className="text-[11px] text-slate-400 dark:text-slate-500">
                {checkedInView} / {filtered.length} {t.backtest.universeSelected}
                {value.length !== checkedInView && (
                  <span className="ml-2">({lang === "zh" ? "總計" : "total"}: {value.length})</span>
                )}
              </p>
            </div>

            {/* Scrollable stock list */}
            <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
              {[...grouped.entries()].map(([sector, stocks]) => (
                <div key={sector}>
                  <div className="flex items-center justify-between sticky top-0 bg-white dark:bg-[#1e293b] z-10 py-0.5">
                    <span className="text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                      {sector} ({stocks.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const tickers = stocks.map((s) => s.ticker);
                        const allChecked = tickers.every((t) => value.includes(t));
                        if (allChecked) {
                          const set = new Set(tickers);
                          onChange(value.filter((v) => !set.has(v)));
                        } else {
                          onChange([...new Set([...value, ...tickers])]);
                        }
                      }}
                      className="text-[10px] px-1.5 py-0.5 text-slate-400 hover:text-blue-500 transition-colors"
                    >
                      {stocks.every((s) => value.includes(s.ticker)) ? (lang === "zh" ? "取消" : "−") : (lang === "zh" ? "全選" : "+")}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-1 gap-y-0.5">
                    {stocks.map((stock) => {
                      const checked = value.includes(stock.ticker);
                      return (
                        <label
                          key={stock.ticker}
                          className={`flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer transition-colors ${
                            checked ? "bg-blue-50 dark:bg-blue-500/10" : "hover:bg-slate-50 dark:hover:bg-slate-800"
                          }`}
                        >
                          <input type="checkbox" checked={checked} onChange={() => toggle(stock.ticker)} className="accent-blue-500 shrink-0" />
                          <span className="text-[11px] font-medium text-slate-700 dark:text-slate-200 shrink-0">{stock.ticker.replace(".TW", "")}</span>
                          <span className="text-[11px] text-slate-400 dark:text-slate-500 truncate">{stock.name}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
              {filtered.length === 0 && (
                <p className="text-center text-sm text-slate-400 py-8">{lang === "zh" ? "無符合結果" : "No matches"}</p>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end px-5 py-3 border-t border-slate-100 dark:border-slate-700">
              <button
                onClick={() => { setOpen(false); setQuery(""); }}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {t.backtest.universeDone}
              </button>
            </div>
          </div>
        </div>
      )}
    </label>
  );
}
