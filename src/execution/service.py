"""
交易執行服務 — 模式感知的統一執行路由。

根據 config.mode 自動選擇執行後端：
- backtest → SimBroker
- paper   → SinopacBroker(simulation=True)
- live    → SinopacBroker(simulation=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from src.core.models import Order, OrderStatus, Portfolio, Trade
from src.execution.broker.base import BrokerAdapter, PaperBroker
from src.execution.market_hours import (
    OrderQueue,
    get_current_session,
    is_tradable,
)
from src.execution.oms import OrderManager
from src.execution.broker.simulated import SimBroker, SimConfig
from src.execution.smart_order import TWAPConfig, TWAPSplitter

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    """執行服務配置。"""
    mode: Literal["backtest", "paper", "live"] = "backtest"
    # Sinopac
    sinopac_api_key: str = ""
    sinopac_secret_key: str = ""
    sinopac_ca_path: str = ""
    sinopac_ca_password: str = ""
    sinopac_simulation: bool = True
    # General
    check_market_hours: bool = True
    queue_off_hours_orders: bool = True
    # Cost model (forwarded to PaperBroker / SinopacBroker simulation)
    # Note: float (not Decimal) is intentional for config simplicity.
    # These rates are converted to Decimal at computation time in broker adapters.
    commission_rate: float = 0.001425
    tax_rate: float = 0.003
    default_slippage_bps: float = 5.0
    # Smart Order (TWAP)
    smart_order_enabled: bool = False
    smart_order_slices: int = 5
    smart_order_interval_minutes: int = 30
    smart_order_min_value: float = 50000


class ExecutionService:
    """統一交易執行服務。

    提供模式感知的訂單路由、交易時段驗證、成交回報處理。

    Usage:
        service = ExecutionService(config)
        service.initialize()
        trades = service.submit_orders(orders, portfolio)
    """

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self._config = config or ExecutionConfig()
        self._broker: BrokerAdapter | None = None
        self._sim_broker: SimBroker | None = None
        self._oms = OrderManager()
        self._order_queue = OrderQueue()
        self._initialized = False
        self._fallback_mode = False
        self._trade_callbacks: list[Any] = []
        # TWAP splitter
        self._twap: TWAPSplitter | None = None
        if self._config.smart_order_enabled:
            self._twap = TWAPSplitter(TWAPConfig(
                n_slices=self._config.smart_order_slices,
                interval_minutes=self._config.smart_order_interval_minutes,
                min_order_value=Decimal(str(self._config.smart_order_min_value)),
            ))

    def initialize(self) -> bool:
        """初始化執行後端。

        Returns:
            是否初始化成功。
        """
        mode = self._config.mode

        if mode == "backtest":
            sim_config = SimConfig(
                commission_rate=self._config.commission_rate,
                tax_rate=self._config.tax_rate,
                slippage_bps=self._config.default_slippage_bps,
            )
            self._sim_broker = SimBroker(sim_config)
            self._initialized = True
            logger.info("ExecutionService initialized: backtest mode (SimBroker)")
            return True

        if mode in ("paper", "live"):
            try:
                from src.execution.broker.sinopac import SinopacBroker, SinopacConfig

                sinopac_config = SinopacConfig(
                    simulation=(mode == "paper"),
                    api_key=self._config.sinopac_api_key,
                    secret_key=self._config.sinopac_secret_key,
                    ca_path=self._config.sinopac_ca_path,
                    ca_password=self._config.sinopac_ca_password,
                    sim_commission_rate=self._config.commission_rate,
                    sim_tax_rate=self._config.tax_rate,
                    sim_slippage_bps=self._config.default_slippage_bps,
                )
                broker = SinopacBroker(sinopac_config)

                if not self._config.sinopac_api_key:
                    # LT-6: no API key → cannot connect. Live mode blocked by config validator.
                    if mode == "live":
                        logger.critical("FATAL: No Sinopac API key for LIVE mode")
                        self._initialized = False
                        return False
                    # Paper mode without API key → fallback
                    from src.execution.cost_model import CostModel
                    self._broker = PaperBroker(cost_model=CostModel.from_config(self._config))
                    self._fallback_mode = True
                    self._initialized = True
                    return True

                connected = broker.connect()
                if not connected:
                    if mode == "live":
                        logger.critical(
                            "FATAL: Shioaji connection failed in LIVE mode. "
                            "Refusing to fall back to PaperBroker — this would create "
                            "phantom trades. Fix the connection and restart."
                        )
                        self._initialized = False
                        return False
                    # Paper mode: fallback 可接受（模擬環境）
                    logger.critical(
                        "FALLBACK: Shioaji connection failed in paper mode — "
                        "falling back to PaperBroker."
                    )
                    from src.execution.cost_model import CostModel
                    self._broker = PaperBroker(cost_model=CostModel.from_config(self._config))
                    self._fallback_mode = True
                    self._initialized = True
                    return True
                broker.start_reconnect_monitor()

                self._broker = broker
                self._initialized = True
                logger.info("ExecutionService initialized: %s mode (SinopacBroker)", mode)

                # Live mode: 註冊 async fill callback 以更新 portfolio
                if not self._config.sinopac_simulation:
                    broker.register_callback(self._on_broker_fill)
                    logger.info("Registered async fill callback for live mode")

                return True

            except ImportError:
                if mode == "live":
                    logger.critical(
                        "FATAL: shioaji not installed — cannot run in LIVE mode."
                    )
                    return False
                logger.critical(
                    "FALLBACK: shioaji not installed — falling back to PaperBroker for paper mode."
                )
                from src.execution.cost_model import CostModel
                self._broker = PaperBroker(cost_model=CostModel.from_config(self._config))
                self._fallback_mode = True
                self._initialized = True
                return True

        logger.error("Unknown mode: %s", mode)
        return False

    def execute(
        self,
        orders: list[Order],
        current_bars: dict[str, dict[str, Any]] | None = None,
        timestamp: datetime | None = None,
    ) -> list[Trade]:
        """OrderExecutor protocol — 統一執行介面（U1）。"""
        return self.submit_orders(orders, portfolio=None, current_bars=current_bars, timestamp=timestamp)

    def submit_orders(
        self,
        orders: list[Order],
        portfolio: Portfolio | None = None,
        current_bars: dict[str, dict[str, Any]] | None = None,
        timestamp: datetime | None = None,
    ) -> list[Trade]:
        """提交訂單並返回成交記錄。

        Args:
            orders: 待執行訂單。
            portfolio: 當前投資組合（回測模式需要）。
            current_bars: 當前行情數據（回測模式需要）。
            timestamp: 成交時間。

        Returns:
            成交記錄列表。
        """
        if not self._initialized:
            raise RuntimeError("ExecutionService not initialized. Call initialize() first.")

        if not orders:
            return []

        mode = self._config.mode

        # 回測模式：直接使用 SimBroker
        if mode == "backtest":
            assert self._sim_broker is not None
            assert current_bars is not None
            # TWAP: 拆單後逐筆送入 SimBroker（各自獨立計算滑點）
            if self._twap is not None:
                orders = self._apply_twap_split(orders, current_bars)
            trades = self._sim_broker.execute(orders, current_bars, timestamp)
            return trades

        # Paper/Live 模式：檢查交易時段 + 券商下單
        # Paper mode 跳過市場時段檢查，允許隨時成交
        skip_hours = mode == "paper"
        if self._config.check_market_hours and not skip_hours and not is_tradable():
            if self._config.queue_off_hours_orders:
                for order in orders:
                    self._order_queue.enqueue({
                        "order": order,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                logger.info(
                    "Market closed, %d orders queued for next session", len(orders)
                )
                return []
            else:
                session = get_current_session()
                logger.warning(
                    "Market closed (session=%s), %d orders rejected",
                    session.value, len(orders),
                )
                for order in orders:
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = f"Market closed: {session.value}"
                return []

        # TWAP: paper/live 模式下也拆單（目前一次全部送出，未來可排程）
        # Note: current_bars may be None in paper/live mode — _apply_twap_split
        # handles this gracefully: falls back to order.price, and if both are None
        # the order is passed through unsplit.
        if self._twap is not None:
            orders = self._apply_twap_split(orders, current_bars)

        # 透過券商提交
        assert self._broker is not None
        broker_trades: list[Trade] = []
        ts = timestamp or datetime.now(timezone.utc)

        for order in orders:
            # LT-9: check broker connection before each order (live mode)
            if not self._fallback_mode and hasattr(self._broker, 'is_connected'):
                if not self._broker.is_connected():
                    logger.critical("Broker disconnected mid-execution — aborting remaining %d orders",
                                    len(orders) - len(broker_trades))
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = "Broker disconnected"
                    break
            self._oms.submit(order)
            self._broker.submit_order(order)

            if order.status == OrderStatus.FILLED:
                trade = Trade(
                    timestamp=ts,
                    symbol=order.instrument.symbol,
                    side=order.side,
                    quantity=order.filled_qty or order.quantity,
                    price=order.filled_avg_price or Decimal("0"),
                    commission=order.commission,
                    slippage_bps=order.slippage_bps,
                    strategy_id=order.strategy_id,
                    order_id=order.id,
                )
                broker_trades.append(trade)
                self._oms.on_fill(trade)

        return broker_trades

    def _apply_twap_split(
        self,
        orders: list[Order],
        current_bars: dict[str, dict[str, Any]] | None = None,
    ) -> list[Order]:
        """將符合條件的母單拆為 TWAP 子單，回傳展平後的訂單列表。

        每筆子單仍以 Order 物件表示（方便下游 SimBroker/OMS 不需改動），
        但數量已縮小為 slice_qty。
        """
        assert self._twap is not None
        result: list[Order] = []
        for order in orders:
            # 取得估計價格：優先用 current_bars 收盤價，否則用 order.price
            price = order.price
            if price is None and current_bars is not None:
                bar = current_bars.get(order.instrument.symbol)
                if bar is not None:
                    close = bar.get("close")
                    if close is not None:
                        price = Decimal(str(close))
            if price is None:
                # 無法估價，不拆
                result.append(order)
                continue

            if not self._twap.should_split(order, price):
                result.append(order)
                continue

            children = self._twap.split(order)
            for child in children:
                # 轉回 Order 物件
                child_order = Order(
                    instrument=child.instrument,
                    side=child.side,
                    order_type=child.order_type,
                    quantity=child.quantity,
                    price=child.price,
                    strategy_id=order.strategy_id,
                )
                result.append(child_order)
        return result

    def flush_queued_orders(self) -> list[dict[str, Any]]:
        """清空盤外佇列，返回待處理的訂單。"""
        return self._order_queue.drain()

    @property
    def mode(self) -> str:
        return self._config.mode

    @property
    def broker(self) -> BrokerAdapter | None:
        return self._broker

    @property
    def sim_broker(self) -> SimBroker | None:
        return self._sim_broker

    @property
    def oms(self) -> OrderManager:
        return self._oms

    @property
    def order_queue(self) -> OrderQueue:
        return self._order_queue

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def fallback_mode(self) -> bool:
        """True if broker connection failed and we fell back to PaperBroker."""
        return self._fallback_mode

    def set_portfolio(self, portfolio: Any, loop: Any = None) -> None:
        """設定 portfolio 和 event loop 供 async fill callback 使用。

        必須在 app startup 時呼叫，否則 live mode 的成交回報無法更新 portfolio。
        """
        self._portfolio = portfolio
        self._event_loop = loop

    def _on_broker_fill(self, order: Order) -> None:
        """Broker 成交回報 callback（在 Shioaji 背景線程中呼叫）。

        當 order.status == FILLED 時，建立 Trade 並排程到 event loop 執行 apply_trades。
        """
        if order.status != OrderStatus.FILLED:
            return

        portfolio = getattr(self, '_portfolio', None)
        loop = getattr(self, '_event_loop', None)
        if portfolio is None or loop is None:
            logger.warning("Async fill: no portfolio/loop set, skipping apply_trades for %s",
                          order.instrument.symbol)
            return

        trade = Trade(
            timestamp=datetime.now(timezone.utc),
            symbol=order.instrument.symbol,
            side=order.side,
            quantity=order.filled_qty or order.quantity,
            price=order.filled_avg_price or Decimal("0"),
            commission=order.commission,
            slippage_bps=order.slippage_bps,
            strategy_id=order.strategy_id,
            order_id=order.id,
        )

        import asyncio

        async def _apply() -> None:
            from src.execution.oms import apply_trades
            apply_trades(portfolio, [trade])
            logger.info("Async fill applied: %s %s %s @ %s",
                       trade.side.value, trade.quantity, trade.symbol, trade.price)

        asyncio.run_coroutine_threadsafe(_apply(), loop)

    def shutdown(self) -> None:
        """優雅關閉。"""
        if self._broker is not None:
            try:
                from src.execution.broker.sinopac import SinopacBroker

                if isinstance(self._broker, SinopacBroker):
                    self._broker.disconnect()
            except ImportError:
                pass
        self._initialized = False
        logger.info("ExecutionService shutdown")
