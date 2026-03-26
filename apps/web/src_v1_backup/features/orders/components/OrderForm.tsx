import { useState } from "react";
import { ordersApi } from "../api";
import { useT } from "@core/i18n";
import { fmtPrice, translateApiError } from "@core/utils";
import { Card, useToast } from "@shared/ui";

interface Props {
  onSubmitted: () => void;
}

export function OrderForm({ onSubmitted }: Props) {
  const { t } = useT();
  const { toast } = useToast();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim() || !quantity || Number(quantity) <= 0) return;
    setConfirming(true);
  };

  const handleConfirm = async () => {
    setConfirming(false);
    setSubmitting(true);
    setError(null);
    try {
      await ordersApi.create({
        symbol: symbol.trim().toUpperCase(),
        side,
        quantity: Number(quantity),
        price: price ? Number(price) : null,
      });
      setSymbol("");
      setQuantity("");
      setPrice("");
      toast("success", t.toast.orderSubmitted);
      onSubmitted();
    } catch (err) {
      const msg = translateApiError(err instanceof Error ? err.message : t.common.orderFailed, t);
      setError(msg);
      toast("error", t.toast.orderFailed);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-5">
      <form onSubmit={handleSubmit} aria-label="New order form" className="space-y-4">
        <p className="text-base font-semibold text-slate-500 dark:text-slate-400">{t.orders.newOrder}</p>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.orders.symbol}</span>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="AAPL"
            required
            className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <div className="space-y-1">
          <span className="text-sm text-slate-500 dark:text-slate-400">{t.orders.side}</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setSide("BUY")}
              aria-pressed={side === "BUY"}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                side === "BUY"
                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                  : "bg-slate-100 dark:bg-surface-dark text-slate-500 dark:text-slate-400"
              }`}
            >
              BUY
            </button>
            <button
              type="button"
              onClick={() => setSide("SELL")}
              aria-pressed={side === "SELL"}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                side === "SELL"
                  ? "bg-red-500/20 text-red-600 dark:text-red-400"
                  : "bg-slate-100 dark:bg-surface-dark text-slate-500 dark:text-slate-400"
              }`}
            >
              SELL
            </button>
          </div>
        </div>
        <label className="space-y-1">
          <span className="text-sm text-slate-500 dark:text-slate-400">{t.orders.qty}</span>
          <input
            type="number"
            value={quantity}
            min={1}
            step={1}
            onChange={(e) => setQuantity(e.target.value)}
            required
            className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {t.orders.price} ({t.orders.mktIfEmpty})
          </span>
          <input
            type="number"
            step="0.01"
            value={price}
            min={0}
            onChange={(e) => setPrice(e.target.value)}
            placeholder={t.orders.market}
            className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <div className="flex items-end">
          <button
            type="submit"
            disabled={submitting || !symbol.trim() || !quantity}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {submitting ? "..." : t.common.submit}
          </button>
        </div>
      </div>
      {confirming && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 space-y-3">
          <p className="text-sm font-medium text-amber-300">{t.orders.confirmTitle}</p>
          <div className="grid grid-cols-4 gap-2 text-sm">
            <div><span className="text-slate-500">{t.orders.symbol}:</span> <span className="font-medium">{symbol.trim().toUpperCase()}</span></div>
            <div><span className="text-slate-500">{t.orders.side}:</span> <span className={`font-medium ${side === "BUY" ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>{side}</span></div>
            <div><span className="text-slate-500">{t.orders.qty}:</span> <span className="font-medium">{quantity}</span></div>
            <div><span className="text-slate-500">{t.orders.price}:</span> <span className="font-medium">{price ? fmtPrice(Number(price)) : t.orders.market}</span></div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={handleConfirm} className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white">{t.common.confirm}</button>
            <button type="button" onClick={() => setConfirming(false)} className="px-4 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-sm font-medium text-white">{t.common.cancel}</button>
          </div>
        </div>
      )}
        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>
    </Card>
  );
}
