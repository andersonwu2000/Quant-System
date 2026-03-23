import { useState } from "react";
import { ordersApi } from "../api";
import { useT } from "@core/i18n";

interface Props {
  onSubmitted: () => void;
}

export function OrderForm({ onSubmitted }: Props) {
  const { t } = useT();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim() || !quantity || Number(quantity) <= 0) return;
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
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.orderFailed);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-surface rounded-xl p-5 space-y-4">
      <p className="text-sm font-medium text-slate-400">{t.orders.newOrder}</p>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <label className="space-y-1">
          <span className="text-xs text-slate-500">{t.orders.symbol}</span>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="AAPL"
            required
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <div className="space-y-1">
          <span className="text-xs text-slate-500">{t.orders.side}</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setSide("BUY")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                side === "BUY"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-surface-dark text-slate-400"
              }`}
            >
              BUY
            </button>
            <button
              type="button"
              onClick={() => setSide("SELL")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                side === "SELL"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-surface-dark text-slate-400"
              }`}
            >
              SELL
            </button>
          </div>
        </div>
        <label className="space-y-1">
          <span className="text-xs text-slate-500">{t.orders.qty}</span>
          <input
            type="number"
            value={quantity}
            min={1}
            onChange={(e) => setQuantity(e.target.value)}
            required
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-slate-500">
            {t.orders.price} ({t.orders.mktIfEmpty})
          </span>
          <input
            type="number"
            step="0.01"
            value={price}
            min={0}
            onChange={(e) => setPrice(e.target.value)}
            placeholder={t.orders.market}
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <div className="flex items-end">
          <button
            type="submit"
            disabled={submitting || !symbol.trim() || !quantity}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {submitting ? "..." : t.common.submit}
          </button>
        </div>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
    </form>
  );
}
