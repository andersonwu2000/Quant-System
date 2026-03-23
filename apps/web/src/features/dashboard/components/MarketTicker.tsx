import { useState, useCallback, useRef, useEffect } from "react";
import { useWs } from "@core/hooks";
import { useT } from "@core/i18n";

interface MarketItem {
  symbol: string;
  price: number;
  change_pct: number;
}

type FlashDir = "up" | "down";

interface TickerState {
  items: Record<string, MarketItem>;
  flashes: Record<string, FlashDir>;
}

export function MarketTicker() {
  const { t } = useT();
  const [state, setState] = useState<TickerState>({ items: {}, flashes: {} });
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      Object.values(flashTimers.current).forEach(clearTimeout);
    };
  }, []);

  const handleMessage = useCallback((data: unknown) => {
    const msg = data as { symbol?: string; price?: number; change_pct?: number };
    if (!msg?.symbol || msg.price == null) return;
    const sym = msg.symbol;

    setState((prev) => {
      const existing = prev.items[sym];
      const direction: FlashDir | undefined =
        existing && msg.price! !== existing.price
          ? msg.price! > existing.price ? "up" : "down"
          : undefined;

      const nextFlashes = direction
        ? { ...prev.flashes, [sym]: direction }
        : prev.flashes;

      if (direction) {
        if (flashTimers.current[sym]) clearTimeout(flashTimers.current[sym]);
        flashTimers.current[sym] = setTimeout(() => {
          if (!mountedRef.current) return;
          setState((s) => {
            if (!(sym in s.flashes)) return s;
            const { [sym]: _, ...rest } = s.flashes;
            return { ...s, flashes: rest };
          });
        }, 1000);
      }

      return {
        items: {
          ...prev.items,
          [sym]: { symbol: sym, price: msg.price!, change_pct: msg.change_pct ?? 0 },
        },
        flashes: nextFlashes,
      };
    });
  }, []);

  useWs("market", handleMessage);

  const list = Object.values(state.items);
  if (list.length === 0) return null;

  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl px-4 py-3 overflow-hidden border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">{t.dashboard.marketTicker}</p>
      <div className="flex gap-6 overflow-x-auto scrollbar-hide">
        {list.map((item) => {
          const flash = state.flashes[item.symbol];
          const isUp = item.change_pct >= 0;
          const colorClass = isUp ? "text-emerald-400" : "text-red-400";
          const flashBg = flash === "up"
            ? "bg-emerald-500/20"
            : flash === "down"
              ? "bg-red-500/20"
              : "bg-transparent";

          return (
            <div
              key={item.symbol}
              className={`flex items-center gap-3 shrink-0 rounded-lg px-2 py-1 transition-colors duration-300 ${flashBg}`}
            >
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">{item.symbol}</span>
              <span className={`text-sm font-mono ${colorClass} transition-colors duration-300`}>
                {item.price.toFixed(2)}
              </span>
              <span className={`text-xs ${colorClass}`}>
                {isUp ? "+" : ""}{item.change_pct.toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
