"""
回測引擎 — 用歷史數據驅動策略，產出績效報告。

核心保證：
1. Context 在時刻 t 只暴露 ≤ t 的數據
2. 成交模擬包含滑價和手續費
3. 相同參數 → 相同結果
"""

from __future__ import annotations

import bisect
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Literal

import pandas as pd

from src.backtest.analytics import BacktestResult, compute_analytics
from src.backtest.validation import detect_price_outliers, detect_survivorship_bias
from src.data.feed import HistoricalFeed
from src.data.fundamentals import FundamentalsProvider
from src.data.quality import check_bars
from src.data.sources import create_fundamentals
from src.core.models import Instrument, Order, Portfolio, Side
from src.core.trading_pipeline import execute_one_bar
from src.execution.oms import apply_trades
from src.execution.broker.simulated import SimBroker, SimConfig
from src.instrument.registry import InstrumentRegistry
from src.risk.engine import RiskEngine
from src.risk.rules import MarketState
from src.strategy.base import Context, Strategy
from src.strategy.engine import weights_to_orders


class BacktestCancelled(Exception):
    """Raised when a backtest is cancelled via cancel_event."""

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回測配置。"""
    universe: list[str]
    start: str = "2020-01-01"
    end: str = "2025-12-31"
    initial_cash: float = 10_000_000.0
    freq: str = "1d"
    rebalance_freq: Literal["daily", "weekly", "monthly"] = "daily"
    slippage_bps: float = 5.0
    commission_rate: float = 0.001425
    tax_rate: float = 0.003
    risk_rules: list[Any] | None = None          # None = 使用預設規則
    max_ffill_days: int = 5                       # forward-fill 最多天數，超過視為無報價
    enable_dividends: bool = False
    market_lot_sizes: dict[str, int] | None = None  # symbol suffix → lot size, e.g. {".TW": 1000}
    fractional_shares: bool = False                  # True = 零股模式 (lot_size=1)

    # ── Execution delay ──
    execution_delay: int = 1                      # 0 = same-day close, 1 = next-day open (default)
    fill_on: Literal["close", "open"] = "open"    # which price to fill on when delayed

    # ── Kill switch ──
    enable_kill_switch: bool = True
    kill_switch_cooldown: Literal["end_of_month", "never"] = "end_of_month"

    # ── Settlement ──
    settlement_days: int = 0                      # 0 = instant; 2 = T+2 (Taiwan)

    # ── SimBroker overrides (forwarded to SimConfig) ──
    impact_model: Literal["fixed", "sqrt"] = "sqrt"
    impact_coeff: float = 50.0
    base_slippage_bps: float = 2.0
    price_limit_pct: float = 0.0                  # 0 = no limit; 0.10 = ±10%


@dataclass
class _BarCache:
    """Per-bar cached market data to avoid redundant matrix lookups."""
    bar_date: datetime | None = None
    prices: dict[str, Decimal] = field(default_factory=dict)
    open_prices: dict[str, Decimal] = field(default_factory=dict)
    volumes: dict[str, Decimal] = field(default_factory=dict)
    prev_close: dict[str, Decimal] = field(default_factory=dict)


class BacktestEngine:
    """
    事件驅動回測引擎。

    流程：
    歷史數據 → 逐 bar 前進 → 策略計算信號 → 風控檢查 → 模擬撮合 → 更新持倉
    """

    def run(
        self,
        strategy: Strategy,
        config: BacktestConfig,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_event: threading.Event | None = None,
        feed_override: HistoricalFeed | None = None,
    ) -> BacktestResult:
        """執行回測。

        Args:
            feed_override: 預載的 HistoricalFeed。若提供則跳過數據下載，
                          直接使用此 feed（用於實驗框架的並行回測）。
        """
        self._price_matrix = pd.DataFrame()
        self._open_matrix = pd.DataFrame()
        self._volume_matrix = pd.DataFrame()
        self._col_index_cache: dict[int, dict[str, int]] = {}  # matrix id → column→index
        self._last_rebalance_month = -1
        self._last_rebalance_week = -1
        self._bar_cache = _BarCache()

        run_id = uuid.uuid4().hex[:8]
        logger.info(
            "BACKTEST START [%s] strategy=%s, universe=%d symbols, %s ~ %s",
            run_id, strategy.name(), len(config.universe),
            config.start, config.end,
        )

        # 1. 準備數據（含品質檢查）
        if feed_override is not None:
            feed = feed_override
            suspect_dates: set[str] = set()
            fundamentals = None
        else:
            feed, suspect_dates, fundamentals = self._load_data(config)
        if not feed.get_universe():
            raise ValueError("No data loaded for any symbol in universe")
        if suspect_dates:
            logger.warning("Skipping %d suspect dates: %s", len(suspect_dates), sorted(suspect_dates)[:10])

        self._config = config

        # ── G8: 回測防禦 — 存活者偏差 & 價格異常偵測 ──
        raw_data: dict[str, pd.DataFrame] = {}
        for sym in config.universe:
            df = feed.get_bars(sym)
            if not df.empty:
                raw_data[sym] = df
        survivorship_warnings = detect_survivorship_bias(raw_data, config.start, config.end)
        price_warnings = detect_price_outliers(raw_data)
        if survivorship_warnings:
            for w in survivorship_warnings:
                logger.warning("SURVIVORSHIP BIAS: %s", w)
        if price_warnings:
            for w in price_warnings:
                logger.warning("PRICE OUTLIER: %s", w)

        # 載入股利數據（如果啟用）
        # Guard: auto_adjust prices already include dividends — injecting again = double-count
        if config.enable_dividends and not config.fractional_shares:
            # Check if price data is already dividend-adjusted (Yahoo default)
            from src.data.sources.yahoo import YAHOO_AUTO_ADJUST
            if YAHOO_AUTO_ADJUST:
                raise ValueError(
                    "enable_dividends=True conflicts with auto_adjust=True (Yahoo default). "
                    "Dividend-adjusted prices already reflect dividends — enabling both "
                    "causes double-counting. Either set enable_dividends=False or use "
                    "unadjusted price data."
                )
        self._dividend_data: dict[str, dict[str, float]] = {}
        if config.enable_dividends:
            self._dividend_data = self._load_dividends(config)

        # 預建價格/成交量矩陣
        self._build_matrices(feed, config.universe)

        # 1b. 建構 Instrument Registry 並偵測多幣別
        registry = InstrumentRegistry()
        self._instruments: dict[str, Instrument] = {}
        for sym in config.universe:
            inst = registry.get_or_create(sym)
            self._instruments[sym] = inst

        # 偵測是否為混幣別 universe
        currencies = {getattr(self._instruments[s], "currency", "TWD") for s in self._instruments}
        self._is_multi_currency = len(currencies) > 1
        self._fx_rates: dict[tuple[str, str], Decimal] = {}
        self._fx_series: pd.Series | None = None  # FX 時序（per-bar 更新用）

        if self._is_multi_currency:
            logger.info("Multi-currency universe detected: %s", currencies)
            try:
                # 載入完整 FX 時序而非單一值
                fx_bars = feed.get_bars(
                    "USDTWD=X",
                    start=config.start,
                    end=config.end,
                )
                if not fx_bars.empty and "close" in fx_bars.columns:
                    self._fx_series = fx_bars["close"]
                    # 用最新值作為 fallback
                    latest = Decimal(str(round(float(fx_bars["close"].iloc[-1]), 4)))
                    self._fx_rates[("USD", "TWD")] = latest
                    logger.info("Loaded FX series USDTWD: %d bars", len(fx_bars))
                else:
                    fx_scalar = feed.get_fx_rate("USD", "TWD")
                    if fx_scalar and fx_scalar != Decimal("1"):
                        self._fx_rates[("USD", "TWD")] = fx_scalar
            except Exception:
                logger.debug("FX rate load failed, using 1:1", exc_info=True)

        # 2. 準備元件
        sim_broker = SimBroker(SimConfig(
            slippage_bps=config.slippage_bps,
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
            impact_model=config.impact_model,
            impact_coeff=config.impact_coeff,
            base_slippage_bps=config.base_slippage_bps,
            price_limit_pct=config.price_limit_pct,
        ))
        risk_engine = RiskEngine(config.risk_rules)
        portfolio = Portfolio(
            cash=Decimal(str(config.initial_cash)),
            initial_cash=Decimal(str(config.initial_cash)),
        )

        # 3. 取得交易日序列
        trading_dates = self._get_trading_dates(feed, config)
        if not trading_dates:
            raise ValueError("No trading dates in range")

        total_bars = len(trading_dates)
        logger.info("Trading dates: %d days", total_bars)

        # 4. 逐 bar 模擬
        nav_history: list[dict[str, Any]] = []
        rebalance_count = 0
        pending_orders: list[Order] = []
        kill_switch_active = False
        kill_switch_month: int = -1
        kill_switch_bar_idx: int = -1  # bar index when kill switch triggered

        for i, bar_date in enumerate(trading_dates):
            # 合作式取消：每個 bar 檢查一次
            if cancel_event is not None and cancel_event.is_set():
                logger.warning(
                    "BACKTEST CANCELLED [%s] at bar %d/%d (%s)",
                    run_id, i, total_bars, bar_date.strftime("%Y-%m-%d"),
                )
                raise BacktestCancelled(
                    f"Backtest cancelled at bar {i}/{total_bars}"
                )

            date_str = bar_date.strftime("%Y-%m-%d")
            if date_str in suspect_dates:
                logger.debug("Skipping suspect date %s", date_str)
                continue

            feed.set_current_date(bar_date)

            # Pre-compute all market data for this bar (cached)
            self._refresh_bar_cache(config.universe, bar_date)

            # ── Settle pending settlements ──
            self._process_settlements(portfolio, date_str, config)

            # ── Execute pending orders from previous day(s) ──
            if pending_orders and config.execution_delay >= 1:
                portfolio, pending_orders = self._execute_pending_orders(
                    pending_orders, config, bar_date, portfolio,
                    sim_broker, trading_dates,
                )

            # 更新市場價格
            portfolio.update_market_prices(self._bar_cache.prices)
            portfolio.as_of = bar_date

            if portfolio.nav_sod == 0:
                portfolio.nav_sod = portfolio.nav

            # ── Kill switch check ──
            if config.enable_kill_switch and risk_engine.kill_switch(portfolio):
                if not kill_switch_active:
                    self._execute_kill_switch(
                        portfolio, sim_broker, bar_date, date_str,
                    )
                    kill_switch_active = True
                    kill_switch_month = bar_date.month
                    kill_switch_bar_idx = i

            # Kill switch cooldown: must be new month AND at least 5 trading days
            if kill_switch_active:
                new_month = bar_date.month != kill_switch_month
                min_bars_passed = (i - kill_switch_bar_idx) >= 5
                if (
                    config.kill_switch_cooldown == "end_of_month"
                    and new_month
                    and min_bars_passed
                ):
                    kill_switch_active = False
                    logger.info(
                        "Kill switch cooldown expired on %s (after %d bars) — resuming trading",
                        date_str, i - kill_switch_bar_idx,
                    )
                elif kill_switch_active:
                    nav_history.append(self._snap_nav(portfolio, bar_date))
                    portfolio.nav_sod = portfolio.nav
                    if progress_callback:
                        progress_callback(i + 1, total_bars)
                    continue

            # 判斷是否再平衡日（在股利注入之前，避免策略看到當日除息現金 — look-ahead bias）
            if self._is_rebalance_day(bar_date, i, config.rebalance_freq):
                rebalanced = self._do_rebalance(
                    strategy, config, bar_date, portfolio, feed,
                    fundamentals, sim_broker, risk_engine,
                    trading_dates, pending_orders,
                )
                if rebalanced is not None:
                    portfolio, pending_orders, did_rebalance = rebalanced
                    if did_rebalance:
                        rebalance_count += 1

            # 股利注入（在 rebalance 之後，避免策略看到當日除息現金）
            if config.enable_dividends:
                self._inject_dividends_impl(portfolio, date_str)

            # 記錄 NAV
            nav_history.append(self._snap_nav(portfolio, bar_date))
            portfolio.nav_sod = portfolio.nav

            if progress_callback:
                progress_callback(i + 1, total_bars)

        # 5. 計算績效
        nav_df = pd.DataFrame(nav_history).set_index("date")
        result = compute_analytics(
            nav_series=nav_df["nav"],
            initial_cash=config.initial_cash,
            trades=sim_broker.trade_log,
            strategy_name=strategy.name(),
            config=config,
            rejected_orders=sim_broker.rejected_log,
        )

        # 附加防禦警告
        result.survivorship_warnings = survivorship_warnings
        result.price_warnings = price_warnings

        logger.info(
            "BACKTEST DONE [%s] return=%.2f%% sharpe=%.2f maxdd=%.2f%% trades=%d rejected=%d",
            run_id,
            result.total_return * 100,
            result.sharpe,
            result.max_drawdown * 100,
            result.total_trades,
            result.rejected_orders,
        )

        # 釋放矩陣記憶體
        self._price_matrix = pd.DataFrame()
        self._open_matrix = pd.DataFrame()
        self._volume_matrix = pd.DataFrame()

        return result

    # ──────────────────────────────────────────────────────
    # Per-bar helper methods (extracted from run())
    # ──────────────────────────────────────────────────────

    def _refresh_bar_cache(
        self, universe: list[str], bar_date: datetime
    ) -> None:
        """Pre-compute all market data for this bar once."""
        self._bar_cache = _BarCache(
            bar_date=bar_date,
            prices=self._lookup_from_matrix(self._price_matrix, universe, bar_date),
            open_prices=self._lookup_from_matrix(self._open_matrix, universe, bar_date),
            volumes=self._lookup_from_matrix(
                self._volume_matrix, universe, bar_date, as_int=True, skip_zero=True,
            ),
            prev_close=self._get_prev_close(universe, bar_date),
        )
        # Fallback: if no open data, use close prices
        if not self._bar_cache.open_prices:
            self._bar_cache.open_prices = self._bar_cache.prices

    @staticmethod
    def _process_settlements(
        portfolio: Portfolio, date_str: str, config: BacktestConfig
    ) -> None:
        """Release settled funds."""
        if config.settlement_days > 0:
            # Keep only unsettled entries (sd > today); entries where sd <= today are released
            portfolio.pending_settlements = [
                (sd, amt) for sd, amt in portfolio.pending_settlements
                if sd > date_str
            ]

    def _execute_pending_orders(
        self,
        pending_orders: list[Order],
        config: BacktestConfig,
        bar_date: datetime,
        portfolio: Portfolio,
        sim_broker: SimBroker,
        trading_dates: list[datetime],
    ) -> tuple[Portfolio, list[Order]]:
        """Execute orders queued from previous day(s). Returns (portfolio, [])."""
        if config.fill_on == "open":
            exec_prices = self._bar_cache.open_prices
        else:
            exec_prices = self._bar_cache.prices

        exec_bars = self._build_bar_dict(
            exec_prices, self._bar_cache.volumes, self._bar_cache.prev_close,
        )
        trades = sim_broker.execute(pending_orders, exec_bars, bar_date)
        if trades:
            portfolio = apply_trades(portfolio, trades)
            if config.settlement_days > 0:
                self._record_settlements(
                    trades, bar_date, config.settlement_days,
                    trading_dates, portfolio,
                )
        return portfolio, []

    def _execute_kill_switch(
        self,
        portfolio: Portfolio,
        sim_broker: SimBroker,
        bar_date: datetime,
        date_str: str,
    ) -> None:
        """Liquidate all positions on kill switch activation."""
        logger.critical(
            "Kill switch activated on %s — liquidating all positions",
            date_str,
        )
        prices = self._bar_cache.prices
        liquidation_orders: list[Order] = []
        for symbol, pos in list(portfolio.positions.items()):
            if pos.quantity > 0:
                liquidation_orders.append(Order(
                    id=uuid.uuid4().hex[:12],
                    instrument=Instrument(symbol=symbol),
                    side=Side.SELL,
                    quantity=pos.quantity,
                    price=prices.get(symbol, Decimal("0")),
                ))
            elif pos.quantity < 0:
                liquidation_orders.append(Order(
                    id=uuid.uuid4().hex[:12],
                    instrument=Instrument(symbol=symbol),
                    side=Side.BUY,
                    quantity=abs(pos.quantity),
                    price=prices.get(symbol, Decimal("0")),
                ))
        if liquidation_orders:
            liq_bars = self._build_bar_dict(
                prices, self._bar_cache.volumes, self._bar_cache.prev_close,
            )
            liq_trades = sim_broker.execute(liquidation_orders, liq_bars, bar_date)
            if liq_trades:
                apply_trades(portfolio, liq_trades)

    def _inject_dividends_impl(
        self, portfolio: Portfolio, date_str: str
    ) -> None:
        """Inject dividend cash for ex-date matches.

        WARNING: If price data is dividend-adjusted (Yahoo's default with
        auto_adjust=True), enabling dividends will DOUBLE-COUNT income —
        the price drop already reflects the dividend. Only enable this with
        unadjusted price data.
        """
        for symbol, pos in portfolio.positions.items():
            div_map = self._dividend_data.get(symbol, {})
            div_amount = div_map.get(date_str)
            if div_amount is not None and pos.quantity != Decimal("0"):
                cash_received = pos.quantity * Decimal(str(div_amount))
                portfolio.cash += cash_received
                logger.info(
                    "DIVIDEND %s: %s shares × $%s = $%s cash",
                    symbol, pos.quantity, div_amount, cash_received,
                )

    def _do_rebalance(
        self,
        strategy: Strategy,
        config: BacktestConfig,
        bar_date: datetime,
        portfolio: Portfolio,
        feed: HistoricalFeed,
        fundamentals: FundamentalsProvider | None,
        sim_broker: SimBroker,
        risk_engine: RiskEngine,
        trading_dates: list[datetime],
        pending_orders: list[Order],
    ) -> tuple[Portfolio, list[Order], bool] | None:
        """Run strategy and generate/execute orders. Returns (portfolio, pending_orders, did_rebalance)."""
        prices = self._bar_cache.prices
        volumes = self._bar_cache.volumes

        ctx = Context(
            feed=feed,
            portfolio=portfolio,
            current_time=bar_date,
            fundamentals_provider=fundamentals,
        )

        # Determine available cash for settlement constraint
        avail_cash: Decimal | None = None
        if config.settlement_days > 0:
            avail_cash = portfolio.available_cash

        if config.execution_delay == 0:
            # Immediate execution — use shared trading pipeline
            current_bars = self._build_bar_dict(
                prices, volumes, self._bar_cache.prev_close,
            )
            trades = execute_one_bar(
                strategy=strategy,
                ctx=ctx,
                portfolio=portfolio,
                risk_engine=risk_engine,
                prices=prices,
                volumes=volumes,
                current_bars=current_bars,
                broker=sim_broker,
                instruments=self._instruments,
                available_cash=avail_cash,
                market_lot_sizes=config.market_lot_sizes,
                fractional_shares=config.fractional_shares,
                timestamp=bar_date,
            )
            if trades and config.settlement_days > 0:
                self._record_settlements(
                    trades, bar_date, config.settlement_days,
                    trading_dates, portfolio,
                )
            return portfolio, [], bool(trades)
        else:
            # Deferred execution — generate orders only, execute on next bar
            target_weights = strategy.on_bar(ctx)
            if not target_weights:
                return None

            orders = weights_to_orders(
                target_weights, portfolio, prices,
                instruments=self._instruments,
                available_cash=avail_cash,
                market_lot_sizes=config.market_lot_sizes,
                fractional_shares=config.fractional_shares,
                volumes=volumes,
            )

            market_state = MarketState(prices=prices, daily_volumes=volumes)
            approved = risk_engine.check_orders(orders, portfolio, market_state)
            return portfolio, approved, bool(approved)

    def _snap_nav(self, portfolio: Portfolio, bar_date: datetime) -> dict[str, Any]:
        """Create a NAV history record."""
        fx = self._get_fx_rates_for_date(bar_date)
        nav = portfolio.nav_in_base(fx) if fx else portfolio.nav
        return {
            "date": bar_date,
            "nav": float(nav),
            "cash": float(portfolio.cash),
            "positions_count": len(portfolio.positions),
            "gross_exposure": float(portfolio.gross_exposure),
        }

    def _get_fx_rates_for_date(
        self, bar_date: datetime,
    ) -> dict[tuple[str, str], Decimal]:
        """取得指定日期的 FX rates（從時序查找，fallback 到靜態值）。"""
        if not self._fx_rates:
            return {}

        if self._fx_series is not None and not self._fx_series.empty:
            # 確保 index 是 DatetimeIndex（快取反序列化後可能退化）
            if not isinstance(self._fx_series.index, pd.DatetimeIndex):
                self._fx_series.index = pd.to_datetime(self._fx_series.index)
            ts = pd.Timestamp(bar_date)
            # 查找 <= bar_date 的最近 FX rate
            mask = self._fx_series.index <= ts
            if mask.any():
                rate = float(self._fx_series.loc[mask].iloc[-1])
                return {("USD", "TWD"): Decimal(str(round(rate, 4)))}

        # fallback: 使用初始載入的靜態值
        return dict(self._fx_rates)

    # ──────────────────────────────────────────────────────
    # Static / utility helpers
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _build_bar_dict(
        prices: dict[str, Decimal],
        volumes: dict[str, Decimal],
        prev_close: dict[str, Decimal],
    ) -> dict[str, dict[str, Any]]:
        """Build bars dict for SimBroker.execute()."""
        bars: dict[str, dict[str, Any]] = {}
        for s, p in prices.items():
            bars[s] = {
                "close": float(p),
                "volume": float(volumes.get(s, Decimal("1e8"))),
                "prev_close": float(prev_close[s]) if s in prev_close else None,
            }
        return bars

    @staticmethod
    def _record_settlements(
        trades: list[Any],
        bar_date: datetime,
        settlement_days: int,
        trading_dates: list[datetime],
        portfolio: Portfolio,
    ) -> None:
        """Record pending settlements for BUY trades.

        NOTE: apply_trades() already deducts cash immediately. This method
        additionally locks the amount in pending_settlements, making
        available_cash more conservative (double-counted). This is intentional
        to prevent the engine from spending unsettled funds in T+N mode.
        The net effect is overly conservative cash gating, not incorrect P&L.
        """
        for trade in trades:
            if trade.side == Side.BUY:
                settle_dt = BacktestEngine._add_business_days(
                    bar_date, settlement_days, trading_dates
                )
                settle_str = settle_dt.strftime("%Y-%m-%d")
                settle_amount = trade.quantity * trade.price + trade.commission
                portfolio.pending_settlements.append((settle_str, settle_amount))

    def _load_dividends(
        self, config: BacktestConfig
    ) -> dict[str, dict[str, float]]:
        """載入所有標的的股利數據。DataCatalog first, Yahoo fallback."""
        from src.data.data_catalog import get_catalog

        catalog = get_catalog()
        result: dict[str, dict[str, float]] = {}
        for symbol in config.universe:
            df = catalog.get("dividend", symbol)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                # Filter to backtest range
                mask = (df["date"] >= config.start) & (df["date"] <= config.end)
                filtered = df[mask]
                if not filtered.empty and "amount" in filtered.columns:
                    divs = {
                        row["date"].strftime("%Y-%m-%d"): float(row["amount"])
                        for _, row in filtered.iterrows()
                        if row.get("amount", 0) > 0
                    }
                    if divs:
                        result[symbol] = divs
        return result

    def _load_data(
        self, config: BacktestConfig
    ) -> tuple[HistoricalFeed, set[str], FundamentalsProvider | None]:
        """Load data into HistoricalFeed — DataCatalog first, Yahoo fallback.

        DataCatalog reads from local parquets (yahoo/ finmind/ twse/ finlab/),
        which is instant. Only falls back to Yahoo download for symbols not
        found locally (e.g. US stocks or missing data).
        """
        from src.data.data_catalog import get_catalog

        catalog = get_catalog()
        feed = HistoricalFeed()
        all_suspect_dates: set[str] = set()
        loaded_from_catalog = 0
        missing_symbols: list[str] = []

        for symbol in config.universe:
            df = catalog.get("price", symbol)
            if not df.empty and "close" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)

                qr = check_bars(df, symbol)
                if qr.suspect_dates:
                    all_suspect_dates.update(qr.suspect_dates)
                if not qr.ok:
                    logger.warning("Quality issues for %s: %s", symbol, qr.issues)

                # Replace zero/negative close with NaN (data corruption guard)
                df["close"] = df["close"].where(df["close"] > 0)
                df["close"] = df["close"].ffill()
                feed.load(symbol, df)
                loaded_from_catalog += 1
            else:
                missing_symbols.append(symbol)

        if missing_symbols:
            logger.warning(
                "Skipped %d symbols not in DataCatalog: %s",
                len(missing_symbols),
                missing_symbols[:10],
            )

        logger.info("Loaded %d/%d symbols from DataCatalog",
                    loaded_from_catalog, len(config.universe))

        from src.core.config import get_config
        cfg = get_config()
        fundamentals = create_fundamentals(cfg.data_source)

        return feed, all_suspect_dates, fundamentals

    def _get_trading_dates(
        self, feed: HistoricalFeed, config: BacktestConfig
    ) -> list[datetime]:
        """取得交易日序列（取所有標的共有的日期，過濾 TWSE 假日）。"""
        all_dates: set[pd.Timestamp] | None = None

        for symbol in feed.get_universe():
            df = feed.get_bars(symbol)
            dates = set(df.index)
            if all_dates is None:
                all_dates = dates
            else:
                all_dates = all_dates | dates

        if not all_dates:
            return []

        sorted_dates = sorted(all_dates)

        start = pd.Timestamp(config.start)
        end = pd.Timestamp(config.end)
        candidates = [d.to_pydatetime() for d in sorted_dates if start <= d <= end]

        # 過濾 TWSE 假日（僅當 universe 包含台股標的時）
        has_tw_symbols = any(
            s.endswith(".TW") or s.endswith(".TWO")
            for s in feed.get_universe()
        )
        if has_tw_symbols:
            from src.core.calendar import get_tw_calendar

            cal = get_tw_calendar()
            candidates = [
                d for d in candidates if cal.is_trading_day(d.date())
            ]

        return candidates

    def _build_matrices(
        self,
        feed: HistoricalFeed,
        universe: list[str],
    ) -> None:
        """預先建立價格、開盤價與成交量矩陣。"""
        price_frames: dict[str, pd.Series] = {}
        open_frames: dict[str, pd.Series] = {}
        volume_frames: dict[str, pd.Series] = {}
        for symbol in universe:
            df = feed.get_bars(symbol)
            if df.empty:
                continue
            price_frames[symbol] = df["close"]
            if "open" in df.columns:
                open_frames[symbol] = df["open"]
            if "volume" in df.columns:
                volume_frames[symbol] = df["volume"]

        if price_frames:
            self._price_matrix = pd.DataFrame(price_frames).sort_index()
            self._price_matrix = self._price_matrix.ffill(limit=self._config.max_ffill_days)
        else:
            self._price_matrix = pd.DataFrame()

        if open_frames:
            self._open_matrix = pd.DataFrame(open_frames).sort_index()
            self._open_matrix = self._open_matrix.ffill(limit=self._config.max_ffill_days)
        else:
            self._open_matrix = pd.DataFrame()

        if volume_frames:
            self._volume_matrix = pd.DataFrame(volume_frames).sort_index()
        else:
            self._volume_matrix = pd.DataFrame()

    # ──────────────────────────────────────────────────────
    # Matrix lookup (unified)
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _lookup_row(matrix: pd.DataFrame, ts: pd.Timestamp) -> pd.Series | None:
        """O(log N) 查詢矩陣中 <= ts 的最近一列。"""
        if matrix.empty:
            return None
        idx = matrix.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            return None
        return matrix.iloc[idx]

    def _lookup_from_matrix(
        self,
        matrix: pd.DataFrame,
        universe: list[str],
        bar_date: datetime,
        *,
        as_int: bool = False,
        skip_zero: bool = False,
    ) -> dict[str, Decimal]:
        """Generic matrix → dict[symbol, Decimal] lookup.

        Args:
            matrix: Pre-built price/open/volume matrix.
            universe: Symbols to look up.
            bar_date: Target date.
            as_int: If True, convert values to int (for volumes).
            skip_zero: If True, skip zero or negative values.
        """
        row = self._lookup_row(matrix, pd.Timestamp(bar_date))
        if row is None:
            return {}
        # Vectorized extraction: get all values at once via numpy
        result: dict[str, Decimal] = {}
        row_vals = row.values  # numpy array
        matrix_id = id(matrix)
        if matrix_id not in self._col_index_cache:
            self._col_index_cache[matrix_id] = {c: i for i, c in enumerate(matrix.columns)}
        col_index = self._col_index_cache[matrix_id]
        _Decimal = Decimal  # local ref for speed
        _Q = _Decimal("0.0001")
        for symbol in universe:
            idx = col_index.get(symbol)
            if idx is None:
                continue
            val = row_vals[idx]
            if val != val:  # NaN check (faster than np.isnan)
                continue
            if skip_zero and val <= 0:
                continue
            if as_int:
                result[symbol] = _Decimal(int(val))
            else:
                result[symbol] = _Decimal(val).quantize(_Q)
        return result

    def _get_prices(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的收盤價。"""
        return self._lookup_from_matrix(self._price_matrix, universe, bar_date)

    def _get_open_prices(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的開盤價。"""
        result = self._lookup_from_matrix(self._open_matrix, universe, bar_date)
        if not result:
            return self._get_prices(universe, bar_date)
        return result

    def _get_prev_close(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得前一日收盤價（用於漲跌停判斷）。"""
        if self._price_matrix.empty:
            return {}
        ts = pd.Timestamp(bar_date)
        idx = self._price_matrix.index.searchsorted(ts, side="right") - 1
        if idx <= 0:
            return {}
        prev_row = self._price_matrix.iloc[idx - 1]
        prices: dict[str, Decimal] = {}
        row_vals = prev_row.values
        # 使用 _col_index_cache 避免每次重建字典
        matrix_id = id(self._price_matrix)
        if matrix_id not in self._col_index_cache:
            self._col_index_cache[matrix_id] = {c: i for i, c in enumerate(self._price_matrix.columns)}
        col_index = self._col_index_cache[matrix_id]
        _Decimal = Decimal
        _Q = _Decimal("0.0001")
        for symbol in universe:
            ci = col_index.get(symbol)
            if ci is None:
                continue
            val = row_vals[ci]
            if val != val:
                continue
            prices[symbol] = _Decimal(val).quantize(_Q)
        return prices

    def _get_volumes(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的成交量。"""
        return self._lookup_from_matrix(
            self._volume_matrix, universe, bar_date,
            as_int=True, skip_zero=True,
        )

    def _is_rebalance_day(
        self, bar_date: datetime, idx: int, freq: str
    ) -> bool:
        """判斷是否為再平衡日。"""
        if freq == "daily":
            return True
        elif freq == "weekly":
            week_key = bar_date.isocalendar()[1]
            if idx == 0 or week_key != self._last_rebalance_week:
                self._last_rebalance_week = week_key
                return True
            return False
        elif freq == "monthly":
            month_key = bar_date.year * 100 + bar_date.month
            if idx == 0 or month_key != self._last_rebalance_month:
                self._last_rebalance_month = month_key
                return True
            return False
        return True

    @staticmethod
    def _add_business_days(
        start: datetime,
        n_days: int,
        trading_dates: list[datetime],
    ) -> datetime:
        """Return the trading date that is n_days after start.

        Uses bisect for O(log N) lookup in the trading calendar.
        """
        idx = bisect.bisect_left(trading_dates, start)
        target_idx = idx + n_days
        if target_idx < len(trading_dates):
            return trading_dates[target_idx]
        result = pd.Timestamp(start) + pd.tseries.offsets.BDay(n_days)
        return result.to_pydatetime()
