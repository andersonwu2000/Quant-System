"""
回測引擎 — 用歷史數據驅動策略，產出績效報告。

核心保證：
1. Context 在時刻 t 只暴露 ≤ t 的數據
2. 成交模擬包含滑價和手續費
3. 相同參數 → 相同結果
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult, compute_analytics
from src.data.feed import HistoricalFeed
from src.data.sources.yahoo import YahooFeed
from src.domain.models import Portfolio
from src.execution.oms import apply_trades
from src.execution.sim import SimBroker, SimConfig
from src.risk.engine import RiskEngine
from src.risk.rules import MarketState
from src.strategy.base import Context, Strategy
from src.strategy.engine import weights_to_orders

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
    ) -> BacktestResult:
        """執行回測。"""
        # 重置實例狀態，避免多次 run() 之間的狀態洩漏
        self._price_matrix = pd.DataFrame()
        self._volume_matrix = pd.DataFrame()
        self._last_rebalance_month = -1

        run_id = uuid.uuid4().hex[:8]
        logger.info(
            "BACKTEST START [%s] strategy=%s, universe=%d symbols, %s ~ %s",
            run_id, strategy.name(), len(config.universe),
            config.start, config.end,
        )

        # 存活者偏差警告
        logger.warning(
            "Yahoo Finance data may exhibit survivorship bias — only currently listed "
            "symbols are available. Consider using a point-in-time dataset for "
            "production research."
        )

        # 1. 準備數據
        feed = self._load_data(config)
        if not feed.get_universe():
            raise ValueError("No data loaded for any symbol in universe")

        # 預建價格/成交量矩陣（向量化查詢）
        self._build_matrices(feed, config.universe)

        # 2. 準備元件
        sim_broker = SimBroker(SimConfig(
            slippage_bps=config.slippage_bps,
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
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

        for i, bar_date in enumerate(trading_dates):
            # 設定 feed 的可見時間
            feed.set_current_date(bar_date)

            # 更新市場價格
            prices = self._get_prices(config.universe, bar_date)
            portfolio.update_market_prices(prices)
            portfolio.as_of = bar_date

            # 記錄當日開盤 NAV
            if portfolio.nav_sod == 0:
                portfolio.nav_sod = portfolio.nav

            # 判斷是否再平衡日
            if self._is_rebalance_day(bar_date, i, config.rebalance_freq):
                # 建立 Context
                ctx = Context(feed=feed, portfolio=portfolio, current_time=bar_date)

                # 策略計算目標權重
                target_weights = strategy.on_bar(ctx)

                if target_weights:
                    # 轉換為訂單
                    orders = weights_to_orders(target_weights, portfolio, prices)

                    # 風控檢查
                    volumes = self._get_volumes(config.universe, bar_date)
                    market_state = MarketState(prices=prices, daily_volumes=volumes)
                    approved = risk_engine.check_orders(orders, portfolio, market_state)

                    # 模擬成交（使用真實成交量）
                    current_bars = {
                        s: {
                            "close": float(p),
                            "volume": float(volumes.get(s, Decimal("1e8"))),
                        }
                        for s, p in prices.items()
                    }
                    trades = sim_broker.execute(approved, current_bars, bar_date)

                    # 更新持倉
                    if trades:
                        portfolio = apply_trades(portfolio, trades)
                        rebalance_count += 1

            # 記錄 NAV
            nav_history.append({
                "date": bar_date,
                "nav": float(portfolio.nav),
                "cash": float(portfolio.cash),
                "positions_count": len(portfolio.positions),
                "gross_exposure": float(portfolio.gross_exposure),
            })

            # 更新次日 SOD NAV
            portfolio.nav_sod = portfolio.nav

            # 回報進度
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
        )

        logger.info(
            "BACKTEST DONE [%s] return=%.2f%% sharpe=%.2f maxdd=%.2f%% trades=%d",
            run_id,
            result.total_return * 100,
            result.sharpe,
            result.max_drawdown * 100,
            result.total_trades,
        )

        # 釋放矩陣記憶體
        self._price_matrix = pd.DataFrame()
        self._volume_matrix = pd.DataFrame()

        return result

    def _load_data(self, config: BacktestConfig) -> HistoricalFeed:
        """從 Yahoo Finance 下載數據並載入 HistoricalFeed。

        額外前拉 400 個交易日（約 18 個月），確保策略有足夠的回溯數據計算因子。
        """
        warmup_days = 400
        warmup_start = (
            pd.Timestamp(config.start) - pd.tseries.offsets.BDay(warmup_days)
        ).strftime("%Y-%m-%d")

        yahoo = YahooFeed(config.universe)
        feed = HistoricalFeed()

        for symbol in config.universe:
            df = yahoo.get_bars(symbol, start=warmup_start, end=config.end)
            if not df.empty:
                feed.load(symbol, df)
                logger.info("Loaded %d bars for %s (warmup from %s)", len(df), symbol, warmup_start)
            else:
                logger.warning("No data for %s, skipping", symbol)

        return feed

    def _get_trading_dates(
        self, feed: HistoricalFeed, config: BacktestConfig
    ) -> list[datetime]:
        """取得交易日序列（取所有標的共有的日期）。"""
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

        # 過濾到回測範圍
        start = pd.Timestamp(config.start)
        end = pd.Timestamp(config.end)
        return [d.to_pydatetime() for d in sorted_dates if start <= d <= end]

    def _build_matrices(
        self,
        feed: HistoricalFeed,
        universe: list[str],
    ) -> None:
        """預先建立價格與成交量矩陣，避免逐 symbol 逐 bar 查詢。"""
        price_frames: dict[str, pd.Series] = {}
        volume_frames: dict[str, pd.Series] = {}
        for symbol in universe:
            df = feed.get_bars(symbol)
            if df.empty:
                continue
            price_frames[symbol] = df["close"]
            if "volume" in df.columns:
                volume_frames[symbol] = df["volume"]

        if price_frames:
            self._price_matrix = pd.DataFrame(price_frames).sort_index()
            # Forward-fill so each date has the latest known price
            self._price_matrix = self._price_matrix.ffill()
        else:
            self._price_matrix = pd.DataFrame()

        if volume_frames:
            self._volume_matrix = pd.DataFrame(volume_frames).sort_index()
        else:
            self._volume_matrix = pd.DataFrame()

    @staticmethod
    def _lookup_row(matrix: pd.DataFrame, ts: pd.Timestamp) -> pd.Series | None:
        """O(log N) 查詢矩陣中 <= ts 的最近一列。"""
        if matrix.empty:
            return None
        idx = matrix.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            return None
        return matrix.iloc[idx]

    def _get_prices(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的收盤價（從預建矩陣查詢）。"""
        row = self._lookup_row(self._price_matrix, pd.Timestamp(bar_date))
        if row is None:
            return {}
        prices: dict[str, Decimal] = {}
        for symbol in universe:
            if symbol in row.index:
                val = row[symbol]
                if not np.isnan(val):
                    prices[symbol] = Decimal(str(round(val, 4)))
                else:
                    logger.debug("No price for %s on %s, skipping", symbol, bar_date)
        return prices

    def _get_volumes(
        self,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的成交量（從預建矩陣查詢）。"""
        row = self._lookup_row(self._volume_matrix, pd.Timestamp(bar_date))
        if row is None:
            return {}
        volumes: dict[str, Decimal] = {}
        for symbol in universe:
            if symbol in row.index:
                vol = row[symbol]
                if not np.isnan(vol) and vol > 0:
                    volumes[symbol] = Decimal(str(int(vol)))
        return volumes

    def _is_rebalance_day(
        self, bar_date: datetime, idx: int, freq: str
    ) -> bool:
        """判斷是否為再平衡日。"""
        if freq == "daily":
            return True
        elif freq == "weekly":
            return bar_date.weekday() == 0 or idx == 0  # 週一或第一天
        elif freq == "monthly":
            # First trading day of each month (rebalance once per month)
            month_key = bar_date.year * 100 + bar_date.month
            if idx == 0 or month_key != self._last_rebalance_month:
                self._last_rebalance_month = month_key
                return True
            return False
        return True
