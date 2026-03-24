import { useState, useCallback, useRef, useMemo, useEffect } from "react";
import { useApi, useWs } from "@core/hooks";
import { fmtCurrency, fmtPrice, fmtDate, fmtTime } from "@core/utils";
import { Card, StatusBadge, ErrorAlert, TableSkeleton, ConnectionBanner, EmptyState } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { ordersApi } from "./api";
import { OrderForm } from "./components/OrderForm";

const filterKeys = ["all", "filled", "pending", "cancelled", "rejected"] as const;

export function OrdersPage() {
  const { t } = useT();
  const { hasRole } = useAuth();
  const canTrade = hasRole("trader");
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const { data: orderList, loading, error, refresh } = useApi(
    () => ordersApi.list(filter === "all" ? undefined : filter),
    [filter],
  );

  // Debounce WS-triggered refresh to at most once per second
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, []);
  const { connected: wsConnected } = useWs(
    "orders",
    useCallback(
      (msg: unknown) => {
        if (msg && typeof msg === "object") {
          if (!refreshTimer.current) {
            refreshTimer.current = setTimeout(() => {
              refreshTimer.current = null;
              if (mountedRef.current) refresh();
            }, 1000);
          }
        }
      },
      [refresh],
    ),
  );

  const filterLabels = useMemo<Record<string, string>>(() => ({
    all: t.orders.all,
    filled: t.orders.filled,
    pending: t.orders.pending,
    cancelled: t.orders.cancelled,
    rejected: t.orders.rejected,
  }), [t]);

  return (
    <div className="space-y-6">
      <ConnectionBanner connected={wsConnected} label={t.common.connectionLost} />
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{t.orders.title}</h2>
        {canTrade && (
          <button
            onClick={() => setShowForm(!showForm)}
            aria-label={showForm ? t.common.cancel : t.orders.newOrder}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {showForm ? t.common.cancel : t.orders.newOrder}
          </button>
        )}
      </div>

      {canTrade && showForm && (
        <OrderForm
          onSubmitted={() => {
            setShowForm(false);
            refresh();
          }}
        />
      )}

      <div className="flex gap-2" role="tablist">
        {filterKeys.map((f) => (
          <button
            key={f}
            role="tab"
            aria-selected={filter === f}
            aria-current={filter === f ? "true" : undefined}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? "bg-blue-500/20 text-blue-600 dark:text-blue-400"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-surface"
            }`}
          >
            {filterLabels[f]}
          </button>
        ))}
      </div>

      {error && <ErrorAlert message={error} onRetry={refresh} />}
      {loading && <TableSkeleton rows={8} cols={10} />}

      {!loading && !error && (
        <Card className="p-5 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-surface-light">
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
                <tr key={o.id} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
                  <td className="py-2 whitespace-nowrap">
                    <span className="text-slate-400">{fmtDate(o.created_at)}</span>{" "}
                    {fmtTime(o.created_at)}
                  </td>
                  <td className="py-2 font-medium">{o.symbol}</td>
                  <td className={`py-2 font-medium ${o.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {o.side}
                  </td>
                  <td className="text-right py-2">{o.quantity}</td>
                  <td className="text-right py-2">{o.price != null ? fmtPrice(o.price) : "MKT"}</td>
                  <td className="text-right py-2">{o.filled_qty}</td>
                  <td className="text-right py-2">
                    {o.filled_avg_price != null ? fmtPrice(o.filled_avg_price) : "\u2014"}
                  </td>
                  <td className="text-right py-2">{fmtCurrency(o.commission)}</td>
                  <td className="py-2 text-sm text-slate-400">{o.strategy_id}</td>
                  <td className="py-2"><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!orderList || orderList.length === 0) && (
            <EmptyState
              message={t.orders.noOrders}
              actionLabel={canTrade ? t.orders.newOrder : undefined}
              onAction={canTrade ? () => setShowForm(true) : undefined}
            />
          )}
        </Card>
      )}
    </div>
  );
}
