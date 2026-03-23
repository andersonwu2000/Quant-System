import { useState, useCallback } from "react";
import { useApi, useWs } from "@core/hooks";
import { fmtCurrency, fmtDate, fmtTime } from "@core/utils";
import { StatusBadge, ErrorAlert, TableSkeleton } from "@shared/ui";
import { useT } from "@core/i18n";
import { ordersApi } from "./api";
import { OrderForm } from "./components/OrderForm";

const filterKeys = ["all", "filled", "pending", "cancelled", "rejected"] as const;

export function OrdersPage() {
  const { t } = useT();
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const { data: orderList, loading, error, refresh } = useApi(
    () => ordersApi.list(filter === "all" ? undefined : filter),
    [filter],
  );

  useWs(
    "orders",
    useCallback(
      (msg: unknown) => {
        if (msg && typeof msg === "object") refresh();
      },
      [refresh],
    ),
  );

  const filterLabels: Record<string, string> = {
    all: t.orders.all,
    filled: t.orders.filled,
    pending: t.orders.pending,
    cancelled: t.orders.cancelled,
    rejected: t.orders.rejected,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">{t.orders.title}</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
        >
          {showForm ? "Cancel" : "New Order"}
        </button>
      </div>

      {showForm && (
        <OrderForm
          onSubmitted={() => {
            setShowForm(false);
            refresh();
          }}
        />
      )}

      <div className="flex gap-2">
        {filterKeys.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? "bg-blue-500/20 text-blue-400"
                : "text-slate-400 hover:text-slate-200 hover:bg-surface"
            }`}
          >
            {filterLabels[f]}
          </button>
        ))}
      </div>

      {error && <ErrorAlert message={error} onRetry={refresh} />}
      {loading && <TableSkeleton rows={8} cols={10} />}

      {!loading && !error && (
        <div className="bg-surface rounded-xl p-5 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 border-b border-surface-light">
                <th className="text-left py-2">{t.orders.time}</th>
                <th className="text-left py-2">{t.orders.symbol}</th>
                <th className="text-left py-2">{t.orders.side}</th>
                <th className="text-right py-2">{t.orders.qty}</th>
                <th className="text-right py-2">{t.orders.price}</th>
                <th className="text-right py-2">{t.orders.filledQty}</th>
                <th className="text-right py-2">{t.orders.avgFill}</th>
                <th className="text-right py-2">{t.orders.commission}</th>
                <th className="text-left py-2">{t.orders.strategy}</th>
                <th className="text-left py-2">{t.orders.status}</th>
              </tr>
            </thead>
            <tbody>
              {orderList?.map((o) => (
                <tr key={o.id} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                  <td className="py-2 whitespace-nowrap">
                    <span className="text-slate-400">{fmtDate(o.created_at)}</span>{" "}
                    {fmtTime(o.created_at)}
                  </td>
                  <td className="py-2 font-medium">{o.symbol}</td>
                  <td className={`py-2 font-medium ${o.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {o.side}
                  </td>
                  <td className="text-right py-2">{o.quantity}</td>
                  <td className="text-right py-2">{o.price != null ? `$${o.price.toFixed(2)}` : "MKT"}</td>
                  <td className="text-right py-2">{o.filled_qty}</td>
                  <td className="text-right py-2">
                    {o.filled_avg_price != null ? `$${o.filled_avg_price.toFixed(2)}` : "\u2014"}
                  </td>
                  <td className="text-right py-2">{fmtCurrency(o.commission)}</td>
                  <td className="py-2 text-xs text-slate-400">{o.strategy_id}</td>
                  <td className="py-2"><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!orderList || orderList.length === 0) && (
            <p className="text-center text-slate-500 py-8">{t.orders.noOrders}</p>
          )}
        </div>
      )}
    </div>
  );
}
