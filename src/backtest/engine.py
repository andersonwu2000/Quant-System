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
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

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
    rebalance_freq: str = "daily"           # "daily", "weekly", "monthly"
    slippage_bps: float = 5.0
    commission_rate: float = 0.001425
    tax_rate: float = 0.003
    risk_rules: list | None = None          # None = 使用預設規則


class BacktestEngine:
    """
    事件驅動回測引擎。

    流程：
    歷史數據 → 逐 bar 前進 → 策略計算信號 → 風控檢查 → 模擬撮合 → 更新持倉
    """

    def run(self, strategy: Strategy, config: BacktestConfig) -> BacktestResult:
        """執行回測。"""
        run_id = uuid.uuid4().hex[:8]
        logger.info(
            "BACKTEST START [%s] strategy=%s, universe=%d symbols, %s ~ %s",
            run_id, strategy.name(), len(config.universe),
            config.start, config.end,
        )

        # 1. 準備數據
        feed = self._load_data(config)
        if not feed.get_universe():
            raise ValueError("No data loaded for any symbol in universe")

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

        logger.info("Trading dates: %d days", len(trading_dates))

        # 4. 逐 bar 模擬
        nav_history: list[dict] = []
        rebalance_count = 0

        for i, bar_date in enumerate(trading_dates):
            # 設定 feed 的可見時間
            feed.set_current_date(bar_date)

            # 更新市場價格
            prices = self._get_prices(feed, config.universe, bar_date)
            portfolio.update_market_prices(prices)
            portfolio.as_of = bar_date

            # 記錄當日開盤 NAV
            if not hasattr(portfolio, "_nav_sod"):
                portfolio._nav_sod = portfolio.nav  # type: ignore[attr-defined]

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
                    market_state = MarketState(prices=prices, daily_volumes={})
                    approved = risk_engine.check_orders(orders, portfolio, market_state)

                    # 模擬成交
                    current_bars = {
                        s: {"close": float(p), "volume": 1e8}
                        for s, p in prices.items()
                    }
                    trades = sim_broker.execute(approved, current_bars, bar_date)

                    # 更新持倉
                    if trades:
                        portfolio = apply_trades(portfolio, trades)
                        rebalance_count += 1

            # 更新每日收盤價
            prices = self._get_prices(feed, config.universe, bar_date)
            portfolio.update_market_prices(prices)

            # 記錄 NAV
            nav_history.append({
                "date": bar_date,
                "nav": float(portfolio.nav),
                "cash": float(portfolio.cash),
                "positions_count": len(portfolio.positions),
                "gross_exposure": float(portfolio.gross_exposure),
            })

            # 更新次日 SOD NAV
            portfolio._nav_sod = portfolio.nav  # type: ignore[attr-defined]

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

        return result

    def _load_data(self, config: BacktestConfig) -> HistoricalFeed:
        """從 Yahoo Finance 下載數據並載入 HistoricalFeed。"""
        yahoo = YahooFeed(config.universe)
        feed = HistoricalFeed()

        for symbol in config.universe:
            df = yahoo.get_bars(symbol, start=config.start, end=config.end)
            if not df.empty:
                feed.load(symbol, df)
                logger.info("Loaded %d bars for %s", len(df), symbol)
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

    def _get_prices(
        self,
        feed: HistoricalFeed,
        universe: list[str],
        bar_date: datetime,
    ) -> dict[str, Decimal]:
        """取得指定日期的收盤價。"""
        prices: dict[str, Decimal] = {}
        for symbol in universe:
            df = feed.get_bars(symbol)
            if df.empty:
                continue
            # 取 <= bar_date 的最近一筆
            mask = df.index <= pd.Timestamp(bar_date)
            if mask.any():
                prices[symbol] = Decimal(str(round(df.loc[mask, "close"].iloc[-1], 4)))
        return prices

    def _is_rebalance_day(
        self, bar_date: datetime, idx: int, freq: str
    ) -> bool:
        """判斷是否為再平衡日。"""
        if freq == "daily":
            return True
        elif freq == "weekly":
            return bar_date.weekday() == 0 or idx == 0  # 週一或第一天
        elif freq == "monthly":
            return bar_date.day <= 3 or idx == 0  # 月初前 3 天或第一天
        return True
