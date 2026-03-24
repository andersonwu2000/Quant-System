import { useState, useCallback } from "react";
import { Plus, Eye, RefreshCw, Trash2 } from "lucide-react";
import { useT } from "@core/i18n";
import { useApi } from "@core/hooks";
import { portfolioEndpoints } from "@core/api";
import type {
  PortfolioListItem,
  SavedPortfolio,
  PortfolioCreateRequest,
  RebalancePreviewRequest,
  RebalancePreviewResponse,
  StrategyInfo,
  TradeRecord,
} from "@core/api";
import { strategiesApi } from "@feat/strategies/api";
import { Modal, ConfirmModal, Card, ErrorAlert, EmptyState } from "@shared/ui";
import { useToast } from "@shared/ui";
import { fmtCurrency, fmtDate, fmtPrice, fmtPct, pnlColor } from "@core/utils";
import { UniversePicker } from "@feat/backtest/components/UniversePicker";

/* ─── Create Portfolio Modal ─────────────────────────────────────────────── */

function CreatePortfolioModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [initialCash, setInitialCash] = useState(10_000_000);
  const [strategyName, setStrategyName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: strategies } = useApi<StrategyInfo[]>(strategiesApi.list);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const req: PortfolioCreateRequest = {
        name: name.trim(),
        initial_cash: initialCash,
      };
      if (strategyName) req.strategy_name = strategyName;
      await portfolioEndpoints.createSaved(req);
      setName("");
      setInitialCash(10_000_000);
      setStrategyName("");
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t.portfolio.createPortfolio}>
      <div className="space-y-4">
        {error && <ErrorAlert message={error} />}

        <div>
          <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">
            {t.portfolio.portfolioName}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
            placeholder="My Portfolio"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">
            {t.portfolio.initialCash}
          </label>
          <input
            type="number"
            value={initialCash}
            onChange={(e) => setInitialCash(Number(e.target.value))}
            className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">
            {t.portfolio.strategyName}
          </label>
          <select
            value={strategyName}
            onChange={(e) => setStrategyName(e.target.value)}
            className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          >
            <option value="">--</option>
            {strategies?.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-surface-light hover:bg-slate-200 dark:hover:bg-surface-light/80 transition-colors"
          >
            {t.common.cancel}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "..." : t.portfolio.createPortfolio}
          </button>
        </div>
      </div>
    </Modal>
  );
}

/* ─── Portfolio Detail Modal ─────────────────────────────────────────────── */

function PortfolioDetailModal({
  open,
  onClose,
  portfolioId,
}: {
  open: boolean;
  onClose: () => void;
  portfolioId: string | null;
}) {
  const { t } = useT();

  const fetchDetail = useCallback(
    () => (portfolioId ? portfolioEndpoints.getSaved(portfolioId) : Promise.resolve(null as unknown as SavedPortfolio)),
    [portfolioId],
  );
  const fetchTrades = useCallback(
    () => (portfolioId ? portfolioEndpoints.trades(portfolioId) : Promise.resolve([] as TradeRecord[])),
    [portfolioId],
  );

  const { data: detail, loading: detailLoading, error: detailError } = useApi<SavedPortfolio>(fetchDetail, [portfolioId]);
  const { data: trades, loading: tradesLoading } = useApi<TradeRecord[]>(fetchTrades, [portfolioId]);

  if (!portfolioId) return null;

  return (
    <Modal open={open} onClose={onClose} title={detail?.name ?? "Portfolio"}>
      {detailError && <ErrorAlert message={detailError} />}
      {detailLoading ? (
        <p className="text-sm text-slate-400 py-4">{t.dashboard.loading}</p>
      ) : detail ? (
        <div className="space-y-4">
          {/* Summary metrics */}
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-slate-500 dark:text-slate-400">{t.portfolio.nav}</p>
              <p className="font-bold">{fmtCurrency(detail.nav)}</p>
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400">{t.portfolio.cash}</p>
              <p className="font-bold">{fmtCurrency(detail.cash)}</p>
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400">{t.portfolio.strategyName}</p>
              <p className="font-bold">{detail.strategy_name || "--"}</p>
            </div>
          </div>

          {/* Positions table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                  <th className="text-left py-2">{t.portfolio.symbol}</th>
                  <th className="text-right py-2">{t.portfolio.quantity}</th>
                  <th className="text-right py-2">{t.portfolio.avgCost}</th>
                  <th className="text-right py-2">{t.portfolio.price}</th>
                  <th className="text-right py-2">{t.portfolio.marketValue}</th>
                  <th className="text-right py-2">{t.portfolio.unrealizedPnl}</th>
                </tr>
              </thead>
              <tbody>
                {detail.positions.map((p) => (
                  <tr key={p.symbol} className="border-b border-slate-100 dark:border-surface-light/50">
                    <td className="py-2 font-medium">{p.symbol}</td>
                    <td className="text-right py-2">{p.quantity}</td>
                    <td className="text-right py-2">{fmtPrice(p.avg_cost)}</td>
                    <td className="text-right py-2">{fmtPrice(p.market_price)}</td>
                    <td className="text-right py-2">{fmtCurrency(p.market_value)}</td>
                    <td className={`text-right py-2 ${pnlColor(p.unrealized_pnl)}`}>
                      {fmtCurrency(p.unrealized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {detail.positions.length === 0 && (
              <p className="text-center text-sm text-slate-400 py-4">{t.portfolio.noPositions}</p>
            )}
          </div>

          {/* Trade history */}
          <div>
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">
              {t.portfolio.tradeHistory}
            </h4>
            {tradesLoading ? (
              <p className="text-sm text-slate-400">{t.dashboard.loading}</p>
            ) : trades && trades.length > 0 ? (
              <div className="overflow-x-auto max-h-48 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                      <th className="text-left py-1">{t.orders.time}</th>
                      <th className="text-left py-1">{t.orders.symbol}</th>
                      <th className="text-left py-1">{t.orders.side}</th>
                      <th className="text-right py-1">{t.orders.qty}</th>
                      <th className="text-right py-1">{t.orders.price}</th>
                      <th className="text-right py-1">{t.orders.commission}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((tr, i) => (
                      <tr key={i} className="border-b border-slate-100 dark:border-surface-light/50">
                        <td className="py-1">{fmtDate(tr.date)}</td>
                        <td className="py-1">{tr.symbol}</td>
                        <td className={`py-1 font-medium ${tr.side === "BUY" ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                          {tr.side}
                        </td>
                        <td className="text-right py-1">{tr.quantity}</td>
                        <td className="text-right py-1">{fmtPrice(tr.price)}</td>
                        <td className="text-right py-1">{fmtCurrency(tr.commission)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-400">{t.portfolio.noTrades}</p>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

/* ─── Rebalance Preview Modal ────────────────────────────────────────────── */

function RebalancePreviewModal({
  open,
  onClose,
  portfolioId,
}: {
  open: boolean;
  onClose: () => void;
  portfolioId: string | null;
}) {
  const { t } = useT();
  const [strategy, setStrategy] = useState("");
  const [universes, setUniverses] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RebalancePreviewResponse | null>(null);

  const { data: strategies } = useApi<StrategyInfo[]>(strategiesApi.list);

  const handleRun = async () => {
    if (!portfolioId || !strategy || universes.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const req: RebalancePreviewRequest = { strategy, universes };
      const res = await portfolioEndpoints.rebalancePreview(portfolioId, req);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    setStrategy("");
    setUniverses([]);
    onClose();
  };

  if (!portfolioId) return null;

  // Collect all symbols from target + current weights
  const allSymbols = result
    ? [...new Set([...Object.keys(result.target_weights), ...Object.keys(result.current_weights)])]
    : [];

  return (
    <Modal open={open} onClose={handleClose} title={t.portfolio.rebalance}>
      <div className="space-y-4">
        {error && <ErrorAlert message={error} />}

        {/* Strategy selector */}
        <div>
          <label className="block text-sm text-slate-500 dark:text-slate-400 mb-1">
            {t.portfolio.strategyName}
          </label>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm"
          >
            <option value="">--</option>
            {strategies?.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Universe picker */}
        <UniversePicker value={universes} onChange={setUniverses} />

        {/* Run button */}
        <button
          onClick={handleRun}
          disabled={loading || !strategy || universes.length === 0}
          className="w-full px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "..." : t.portfolio.rebalance}
        </button>

        {/* Results */}
        {result && (
          <div className="space-y-4 pt-2">
            {/* Weights comparison table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                    <th className="text-left py-2">{t.portfolio.symbol}</th>
                    <th className="text-right py-2">{t.portfolio.currentWeight}</th>
                    <th className="text-right py-2">{t.portfolio.targetWeight}</th>
                    <th className="text-right py-2">Diff</th>
                  </tr>
                </thead>
                <tbody>
                  {allSymbols.map((sym) => {
                    const cw = result.current_weights[sym] ?? 0;
                    const tw = result.target_weights[sym] ?? 0;
                    const diff = tw - cw;
                    return (
                      <tr key={sym} className="border-b border-slate-100 dark:border-surface-light/50">
                        <td className="py-1.5 font-medium">{sym}</td>
                        <td className="text-right py-1.5">{fmtPct(cw)}</td>
                        <td className="text-right py-1.5">{fmtPct(tw)}</td>
                        <td className={`text-right py-1.5 ${pnlColor(diff)}`}>{fmtPct(diff)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Suggested trades */}
            <div>
              <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">
                {t.portfolio.suggestedTrades}
              </h4>
              {result.suggested_trades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                        <th className="text-left py-2">{t.portfolio.symbol}</th>
                        <th className="text-left py-2">{t.orders.side}</th>
                        <th className="text-right py-2">{t.orders.qty}</th>
                        <th className="text-right py-2">{t.orders.price}</th>
                        <th className="text-right py-2">{t.portfolio.estimatedCost}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.suggested_trades.map((trade, i) => (
                        <tr key={i} className="border-b border-slate-100 dark:border-surface-light/50">
                          <td className="py-1.5 font-medium">{trade.symbol}</td>
                          <td className={`py-1.5 font-medium ${trade.side === "BUY" ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                            {trade.side}
                          </td>
                          <td className="text-right py-1.5">{trade.quantity}</td>
                          <td className="text-right py-1.5">{fmtPrice(trade.estimated_price)}</td>
                          <td className="text-right py-1.5">{fmtCurrency(trade.estimated_cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-400">{t.portfolio.noTrades}</p>
              )}
            </div>

            {/* Summary: commission + tax */}
            <div className="flex gap-6 text-sm pt-1">
              <div>
                <span className="text-slate-500 dark:text-slate-400">{t.portfolio.totalCommission}: </span>
                <span className="font-semibold">{fmtCurrency(result.estimated_total_commission)}</span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">{t.portfolio.totalTax}: </span>
                <span className="font-semibold">{fmtCurrency(result.estimated_total_tax)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

/* ─── Main Panel ─────────────────────────────────────────────────────────── */

export function SavedPortfoliosPanel() {
  const { t } = useT();
  const { toast } = useToast();

  // State for modals
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [rebalanceId, setRebalanceId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PortfolioListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data: portfolios, loading, error, refresh } = useApi<PortfolioListItem[]>(
    portfolioEndpoints.listSaved,
  );

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await portfolioEndpoints.deleteSaved(deleteTarget.id);
      toast("success", `${deleteTarget.name} deleted`);
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold">{t.portfolio.savedPortfolios}</h3>
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={15} />
          {t.portfolio.createPortfolio}
        </button>
      </div>

      {/* Error */}
      {error && <ErrorAlert message={error} onRetry={refresh} />}

      {/* Loading */}
      {loading && (
        <p className="text-sm text-slate-400">{t.dashboard.loading}</p>
      )}

      {/* Portfolio cards grid */}
      {!loading && portfolios && portfolios.length === 0 && (
        <Card className="p-5">
          <EmptyState
            message={t.portfolio.noSavedPortfolios}
            actionLabel={t.portfolio.createPortfolio}
            onAction={() => setCreateOpen(true)}
          />
        </Card>
      )}

      {!loading && portfolios && portfolios.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {portfolios.map((pf) => (
            <Card key={pf.id} className="p-5 flex flex-col gap-3">
              {/* Name + strategy */}
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {pf.name}
                </h4>
                {pf.strategy_name && (
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    {pf.strategy_name}
                  </span>
                )}
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-slate-500 dark:text-slate-400 text-xs">{t.portfolio.cash}</p>
                  <p className="font-semibold">{fmtCurrency(pf.cash)}</p>
                </div>
                <div>
                  <p className="text-slate-500 dark:text-slate-400 text-xs">{t.portfolio.initialCash}</p>
                  <p className="font-semibold">{fmtCurrency(pf.initial_cash)}</p>
                </div>
                <div>
                  <p className="text-slate-500 dark:text-slate-400 text-xs">{t.dashboard.positions}</p>
                  <p className="font-semibold">{pf.position_count}</p>
                </div>
                <div>
                  <p className="text-slate-500 dark:text-slate-400 text-xs">{t.admin.createdAt}</p>
                  <p className="font-semibold text-xs">{fmtDate(pf.created_at)}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-1 border-t border-slate-100 dark:border-surface-light/50">
                <button
                  onClick={() => setDetailId(pf.id)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 hover:bg-blue-100 dark:hover:bg-blue-500/20 rounded-lg transition-colors"
                >
                  <Eye size={13} /> View
                </button>
                <button
                  onClick={() => setRebalanceId(pf.id)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 hover:bg-amber-100 dark:hover:bg-amber-500/20 rounded-lg transition-colors"
                >
                  <RefreshCw size={13} /> {t.portfolio.rebalance}
                </button>
                <button
                  onClick={() => setDeleteTarget(pf)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-colors ml-auto"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modals */}
      <CreatePortfolioModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />

      <PortfolioDetailModal
        open={detailId !== null}
        onClose={() => setDetailId(null)}
        portfolioId={detailId}
      />

      <RebalancePreviewModal
        open={rebalanceId !== null}
        onClose={() => setRebalanceId(null)}
        portfolioId={rebalanceId}
      />

      <ConfirmModal
        open={deleteTarget !== null}
        title={t.portfolio.deletePortfolio}
        message={t.portfolio.deleteConfirm}
        variant="danger"
        confirmLabel={t.portfolio.deletePortfolio}
        cancelLabel={t.common.cancel}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </div>
  );
}
