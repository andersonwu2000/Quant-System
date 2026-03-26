import { Fragment, useState, useCallback, useRef, useMemo, useEffect } from "react";
import { useApi, useWs } from "@core/hooks";
import { fmtCurrency, fmtPrice, fmtDate, fmtTime } from "@core/utils";
import { Card, StatusBadge, ErrorAlert, TableSkeleton, ConnectionBanner, EmptyState, useToast } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { ordersApi } from "./api";
import { OrderForm } from "./components/OrderForm";
import { X, Pencil } from "lucide-react";

const filterKeys = ["all", "filled", "pending", "cancelled", "rejected"] as const;

export function OrdersPage() {
  const { t } = useT();
  const { hasRole } = useAuth();
  const canTrade = hasRole("trader");
  const { toast } = useToast();
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState("");
  const [editQty, setEditQty] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
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

  const handleCancel = async (orderId: string) => {
    setActionLoading(orderId);
    try {
      await ordersApi.cancel(orderId);
      toast("success", t.orders.cancelSuccess ?? "Order cancelled");
      refresh();
    } catch {
      toast("error", t.common.requestFailed);
    } finally {
      setActionLoading(null);
    }
  };

  const handleEdit = (o: { id: string; price?: number | null; quantity: number }) => {
    setEditingId(o.id);
    setEditPrice(o.price != null ? String(o.price) : "");
    setEditQty(String(o.quantity));
  };

  const handleEditSubmit = async () => {
    if (!editingId) return;
    setActionLoading(editingId);
    try {
      const data: { price?: number; quantity?: number } = {};
      if (editPrice) data.price = parseFloat(editPrice);
      if (editQty) data.quantity = parseFloat(editQty);
      await ordersApi.update(editingId, data);
      toast("success", t.orders.updateSuccess ?? "Order updated");
      setEditingId(null);
      refresh();
    } catch {
      toast("error", t.common.requestFailed);
    } finally {
      setActionLoading(null);
    }
  };

  const isOpenOrder = (status: string) =>
    status === "SUBMITTED" || status === "PENDING" || status === "PARTIAL";

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
                {canTrade && <th className="text-center py-2">{t.orders.actions ?? "Actions"}</th>}
              </tr>
            </thead>
            <tbody>
              {orderList?.map((o) => (
                <Fragment key={o.id}>
                <tr className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
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
                  {canTrade && (
                    <td className="py-2 text-center">
                      {isOpenOrder(o.status) && (
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => handleEdit(o)}
                            disabled={actionLoading === o.id}
                            title={t.orders.edit ?? "Edit"}
                            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-surface-light text-slate-400 hover:text-blue-400 transition-colors"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            onClick={() => handleCancel(o.id)}
                            disabled={actionLoading === o.id}
                            title={t.orders.cancel ?? "Cancel"}
                            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-surface-light text-slate-400 hover:text-red-400 transition-colors"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      )}
                    </td>
                  )}
                </tr>
                {/* Inline edit row */}
                {editingId === o.id && (
                  <tr className="bg-blue-500/5">
                    <td colSpan={canTrade ? 11 : 10} className="py-3 px-4">
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-slate-400">{t.orders.editOrder ?? "Edit order"}:</span>
                        <label className="flex items-center gap-1">
                          {t.orders.price}
                          <input
                            type="number"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            placeholder="MKT"
                            className="w-24 px-2 py-1 rounded bg-surface-light border border-slate-600 text-sm"
                          />
                        </label>
                        <label className="flex items-center gap-1">
                          {t.orders.qty}
                          <input
                            type="number"
                            value={editQty}
                            onChange={(e) => setEditQty(e.target.value)}
                            className="w-20 px-2 py-1 rounded bg-surface-light border border-slate-600 text-sm"
                          />
                        </label>
                        <button
                          onClick={handleEditSubmit}
                          disabled={actionLoading === o.id}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs font-medium text-white"
                        >
                          {t.common.save ?? "Save"}
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-3 py-1 bg-slate-600 hover:bg-slate-500 rounded text-xs font-medium text-white"
                        >
                          {t.common.cancel}
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
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
