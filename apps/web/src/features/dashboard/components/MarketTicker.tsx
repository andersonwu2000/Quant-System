import { useState, useCallback, useRef } from "react";
import { useWs } from "@core/hooks";
import { useT } from "@core/i18n";

interface MarketItem {
  symbol: string;
  price: number;
  change_pct: number;
  prev_price?: number;
}

type FlashState = Record<string, "up" | "down">;

export function MarketTicker() {
  const { t } = useT();
  const [items, setItems] = useState<Record<string, MarketItem>>({});
  const [flashes, setFlashes] = useState<FlashState>({});
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const handleMessage = useCallback((data: unknown) => {
    const msg = data as { symbol?: string; price?: number; change_pct?: number };
    if (!msg?.symbol || msg.price == null) return;

    setItems((prev) => {
      const existing = prev[msg.symbol!];
      const direction =
        existing && msg.price! !== existing.price
          ? msg.price! > existing.price
            ? "up"
            : "down"
          : undefined;

      if (direction) {
        setFlashes((f) => ({ ...f, [msg.symbol!]: direction }));
        // Clear existing timer
        if (flashTimers.current[msg.symbol!]) {
          clearTimeout(flashTimers.current[msg.symbol!]);
        }
        flashTimers.current[msg.symbol!] = setTimeout(() => {
          setFlashes((f) => {
            const next = { ...f };
            delete next[msg.symbol!];
            return next;
          });
        }, 1000);
      }

      return {
        ...prev,
        [msg.symbol!]: {
          symbol: msg.symbol!,
          price: msg.price!,
          change_pct: msg.change_pct ?? 0,
          prev_price: existing?.price,
        },
      };
    });
  }, []);

  useWs("market", handleMessage);

  const list = Object.values(items);
  if (list.length === 0) return null;

  return (
    <div className="bg-surface rounded-xl px-4 py-3 overflow-hidden">
      <p className="text-xs font-medium text-slate-400 mb-2">{t.dashboard.marketTicker}</p>
      <div className="flex gap-6 overflow-x-auto scrollbar-hide">
        {list.map((item) => {
          const flash = flashes[item.symbol];
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
              <span className="text-sm font-semibold text-slate-200">{item.symbol}</span>
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
