"""
永豐金 Shioaji 券商對接 — 實作 BrokerAdapter。

Shioaji SDK 為條件導入：未安裝時仍可載入模組（用於測試），
但 connect() 會拋出 ImportError。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from src.core.models import Order, OrderStatus, OrderType, Side
from src.execution.broker.base import BrokerAdapter

logger = logging.getLogger(__name__)


# ── Shioaji 常數映射 ──────────────────────────────────────────

class SinopacOrderType(Enum):
    """Shioaji 委託有效期。"""
    ROD = "ROD"   # 當日有效
    IOC = "IOC"   # 立即成交否則取消
    FOK = "FOK"   # 全部成交否則取消


class SinopacSubType(Enum):
    """Shioaji 股票子類型。"""
    COMMON = "Common"         # 整股
    ODD = "Odd"               # 零股
    BLOCK_TRADE = "BlockTrade"
    FIXING = "Fixing"         # 定盤


@dataclass
class SinopacOrderResult:
    """Shioaji 委託回報的標準化結果。"""
    broker_order_id: str = ""
    status: str = ""
    message: str = ""
    order: Order | None = None


@dataclass
class SinopacConfig:
    """SinopacBroker 配置。"""
    simulation: bool = True
    default_order_type: SinopacOrderType = SinopacOrderType.ROD
    default_sub_type: SinopacSubType = SinopacSubType.COMMON
    reconnect_interval: float = 5.0   # 斷線重連間隔（秒）
    max_reconnect_attempts: int = 10
    ca_path: str = ""
    ca_password: str = ""
    api_key: str = ""
    secret_key: str = ""
    non_blocking: bool = True         # timeout=0 for non-blocking place_order (~12ms vs ~136ms)


class SinopacBroker(BrokerAdapter):
    """永豐金 Shioaji 實盤/模擬 Adapter。

    封裝 Shioaji SDK，提供統一的 BrokerAdapter 介面。
    透過 simulation 參數切換模擬/實盤模式。
    """

    def __init__(self, config: SinopacConfig | None = None) -> None:
        self._config = config or SinopacConfig()
        self._api: Any = None  # shioaji.Shioaji instance
        self._connected = False
        self._trades: dict[str, Any] = {}  # broker_order_id → shioaji Trade
        self._order_map: dict[str, Order] = {}  # broker_order_id → our Order
        self._callbacks: list[Callable[[Order], None]] = []
        self._lock = threading.Lock()
        self._reconnect_thread: threading.Thread | None = None
        self._stop_reconnect = threading.Event()

    # ── 連線管理 ──────────────────────────────────────────

    def connect(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        ca_path: str | None = None,
        ca_password: str | None = None,
    ) -> bool:
        """登入 Shioaji 並啟用 CA 憑證。

        Args:
            api_key: Shioaji API key（覆蓋 config）。
            secret_key: Shioaji secret key。
            ca_path: CA 憑證路徑。
            ca_password: CA 憑證密碼。

        Returns:
            是否連線成功。

        Raises:
            ImportError: shioaji 未安裝。
        """
        try:
            import shioaji as sj
        except ImportError as exc:
            raise ImportError(
                "shioaji is not installed. Install it with: pip install shioaji"
            ) from exc

        ak = api_key or self._config.api_key
        sk = secret_key or self._config.secret_key
        ca = ca_path or self._config.ca_path
        ca_pwd = ca_password or self._config.ca_password

        try:
            self._api = sj.Shioaji(simulation=self._config.simulation)
            self._api.login(api_key=ak, secret_key=sk)
            logger.info(
                "Shioaji login successful (simulation=%s)", self._config.simulation
            )

            # CA 憑證（實盤下單必要，模擬模式可跳過）
            if ca and not self._config.simulation:
                self._api.activate_ca(
                    ca_path=ca,
                    ca_passwd=ca_pwd,
                )
                logger.info("CA certificate activated")

            # 註冊成交回報 callback
            self._api.set_order_callback(self._on_order_callback)

            self._connected = True
            self._stop_reconnect.clear()
            return True

        except Exception:
            logger.exception("Shioaji connection failed")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """斷開 Shioaji 連線。"""
        self._stop_reconnect.set()
        if self._api is not None:
            try:
                self._api.logout()
            except Exception:
                logger.debug("Logout error (may already be disconnected)", exc_info=True)
        self._connected = False
        self._api = None
        logger.info("Shioaji disconnected")

    # ── BrokerAdapter 介面 ────────────────────────────────

    def submit_order(self, order: Order) -> str:
        """提交訂單至 Shioaji。

        Returns:
            券商端 order_id。
        """
        self._ensure_connected()
        import shioaji as sj

        contract = self._resolve_contract(order.instrument.symbol)
        if contract is None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Contract not found: {order.instrument.symbol}"
            return ""

        # 委託參數轉換
        action = sj.constant.Action.Buy if order.side == Side.BUY else sj.constant.Action.Sell
        price_type = self._map_price_type(order)
        order_type = getattr(sj.constant.OrderType, self._config.default_order_type.value)

        # 數量轉換：本專案以「股」為單位，Shioaji 整股以「張」(1000 股) 為單位
        quantity, is_odd_lot = self._shares_to_lots(order.quantity, order.instrument.symbol)
        if quantity <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Zero quantity after lot conversion: {order.quantity}"
            return ""

        sj_order = self._api.Order(
            price=float(order.price) if order.price else 0,
            quantity=int(quantity),
            action=action,
            price_type=price_type,
            order_type=order_type,
        )
        # 零股需要使用盤中零股子類型
        if is_odd_lot:
            try:
                sj_order.stock_order_lot = sj.constant.StockOrderLot.IntradayOdd
            except AttributeError:
                pass  # 舊版 Shioaji 可能沒有此常數

        try:
            if self._config.non_blocking:
                trade = self._api.place_order(contract, sj_order, timeout=0)
            else:
                trade = self._api.place_order(contract, sj_order)
            broker_id = trade.order.id if hasattr(trade, "order") else str(id(trade))

            with self._lock:
                self._trades[broker_id] = trade
                self._order_map[broker_id] = order

            order.client_order_id = broker_id

            # Simulation mode: 模擬即時成交，含滑價和最低佣金
            if self._config.simulation:
                price = order.price or Decimal("0")
                # 滑價 5 bps（和 PaperBroker/SimBroker 一致）
                slippage = price * Decimal("5") / Decimal("10000")
                if order.side == Side.BUY:
                    fill_price = price + slippage
                else:
                    fill_price = max(price - slippage, Decimal("0.01"))

                order.status = OrderStatus.FILLED
                order.filled_qty = order.quantity
                order.filled_avg_price = fill_price
                notional = order.quantity * fill_price
                commission = notional * Decimal("0.001425")
                if commission < Decimal("20"):
                    commission = Decimal("20")
                tax = notional * Decimal("0.003") if order.side == Side.SELL else Decimal("0")
                order.commission = commission + tax
                logger.info(
                    "Order FILLED (sim): %s %s %s @ %s (slippage %s)",
                    order.side.value, order.quantity, order.instrument.symbol,
                    fill_price, slippage,
                )
            else:
                order.status = OrderStatus.SUBMITTED
                logger.info(
                    "Order submitted: %s %s %s @ %s (broker_id=%s)",
                    order.side.value, order.quantity, order.instrument.symbol,
                    order.price, broker_id,
                )
            return broker_id

        except Exception:
            logger.exception("Order submission failed: %s", order.instrument.symbol)
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Shioaji submission error"
            return ""

    def cancel_order(self, order_id: str) -> bool:
        """撤單。"""
        self._ensure_connected()

        with self._lock:
            trade = self._trades.get(order_id)
        if trade is None:
            logger.warning("Cancel failed: broker order %s not found", order_id)
            return False

        try:
            self._api.cancel_order(trade)
            logger.info("Cancel requested: broker_id=%s", order_id)
            return True
        except Exception:
            logger.exception("Cancel failed: broker_id=%s", order_id)
            return False

    def update_order(
        self, order_id: str, price: Decimal | None = None, quantity: int | None = None
    ) -> bool:
        """改價或改量。"""
        self._ensure_connected()

        with self._lock:
            trade = self._trades.get(order_id)
        if trade is None:
            return False

        try:
            self._api.update_order(
                trade,
                price=float(price) if price is not None else trade.order.price,
                qty=quantity if quantity is not None else trade.order.quantity,
            )
            logger.info("Order updated: broker_id=%s", order_id)
            return True
        except Exception:
            logger.exception("Update failed: broker_id=%s", order_id)
            return False

    def query_positions(self) -> dict[str, dict[str, Any]]:
        """查詢券商端持倉。"""
        self._ensure_connected()

        try:
            positions = self._api.list_positions(self._api.stock_account)
            result: dict[str, dict[str, Any]] = {}
            for p in positions:
                result[p.code] = {
                    "quantity": p.quantity,  # already in shares
                    "avg_cost": Decimal(str(p.price)),
                    "pnl": getattr(p, "pnl", 0),
                    "market_value": getattr(p, "last_price", 0) * p.quantity,
                }
            return result
        except Exception:
            logger.exception("Position query failed")
            return {}

    def query_account(self) -> dict[str, Any]:
        """查詢帳戶資訊。"""
        self._ensure_connected()

        try:
            margin = self._api.account_balance()
            return {
                "balance": getattr(margin, "acc_balance", 0),
                "available": getattr(margin, "available_margin", 0),
                "status": "active" if self._connected else "disconnected",
                "simulation": self._config.simulation,
            }
        except Exception:
            logger.exception("Account query failed")
            return {"status": "error", "simulation": self._config.simulation}

    def is_connected(self) -> bool:
        return self._connected

    # ── 交易額度查詢 ─────────────────────────────────────

    def query_trading_limits(self) -> dict[str, Any]:
        """查詢交易額度 (trading limits)。

        Returns:
            交易額度、已使用額度、可用額度（含融資融券）。
        """
        self._ensure_connected()

        try:
            limits = self._api.trading_limits(self._api.stock_account)
            return {
                "trading_limit": getattr(limits, "trading_limit", 0),
                "trading_used": getattr(limits, "trading_used", 0),
                "trading_available": getattr(limits, "trading_available", 0),
                "margin_limit": getattr(limits, "margin_limit", 0),
                "margin_used": getattr(limits, "margin_used", 0),
                "margin_available": getattr(limits, "margin_available", 0),
                "short_limit": getattr(limits, "short_limit", 0),
                "short_used": getattr(limits, "short_used", 0),
                "short_available": getattr(limits, "short_available", 0),
            }
        except Exception:
            logger.exception("Trading limits query failed")
            return {}

    def query_settlements(self) -> list[dict[str, Any]]:
        """查詢交割資訊。

        Returns:
            交割日期與金額列表。
        """
        self._ensure_connected()

        try:
            settlements = self._api.settlements(self._api.stock_account)
            return [
                {"date": getattr(s, "date", ""), "amount": getattr(s, "amount", 0)}
                for s in settlements
            ]
        except Exception:
            logger.exception("Settlements query failed")
            return []

    def check_dispositions(self) -> set[str]:
        """查詢處置股票清單（違約交割限制）。

        Returns:
            受限制的股票代碼集合。
        """
        self._ensure_connected()

        try:
            punish = self._api.punish()
            codes: list[str] = getattr(punish, "code", [])
            return set(codes)
        except Exception:
            logger.exception("Dispositions query failed")
            return set()

    # ── Callback 管理 ─────────────────────────────────────

    def register_callback(self, fn: Callable[[Order], None]) -> None:
        """註冊成交回報 callback。"""
        self._callbacks.append(fn)

    def _on_order_callback(self, stat: Any, msg: dict[str, Any]) -> None:
        """Shioaji 成交回報 callback — 在 SDK 背景執行緒中調用。

        stat is sj.constant.OrderState (StockOrder or StockDeal).
        - StockOrder: msg contains msg["order"]["id"], msg["operation"]["op_code"]
        - StockDeal: msg contains msg["code"], msg["price"], msg["quantity"]
        """
        try:
            stat_name = getattr(stat, "name", str(stat))

            if stat_name == "StockDeal":
                # Deal callback — find order by stock code or recent submission
                broker_id = self._find_broker_id_for_deal(msg)
                with self._lock:
                    order = self._order_map.get(broker_id) if broker_id else None

                if order is None:
                    logger.debug("Deal callback for unknown order: %s", msg)
                    return

                filled_qty = Decimal(str(msg.get("quantity", 0)))
                filled_price = Decimal(str(msg.get("price", 0)))

                order.filled_qty += filled_qty
                order.filled_avg_price = filled_price

                if order.filled_qty >= order.quantity:
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.PARTIAL

            elif stat_name == "StockOrder":
                broker_id = msg.get("order", {}).get("id", "")
                with self._lock:
                    order = self._order_map.get(broker_id)

                if order is None:
                    logger.debug("Callback for unknown order: %s", broker_id)
                    return

                op_code = msg.get("operation", {}).get("op_code", "")
                if op_code == "Cancel":
                    order.status = OrderStatus.CANCELLED
                elif op_code in ("Fail", "Reject"):
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = msg.get("operation", {}).get("op_msg", str(op_code))

            else:
                logger.debug("Unknown order state: %s", stat_name)
                return

            logger.info(
                "Order callback: %s → %s (filled=%s/%s)",
                broker_id, order.status.value, order.filled_qty, order.quantity,
            )

            # 通知外部 callback
            for fn in self._callbacks:
                try:
                    fn(order)
                except Exception:
                    logger.exception("Order callback handler error")

        except Exception:
            logger.exception("Error processing order callback")

    def _find_broker_id_for_deal(self, msg: dict[str, Any]) -> str:
        """從成交回報中找到對應的 broker_order_id。"""
        code = msg.get("code", "")
        with self._lock:
            for bid, order in self._order_map.items():
                if order.instrument.symbol == code and order.status in (
                    OrderStatus.SUBMITTED, OrderStatus.PARTIAL
                ):
                    return bid
        return ""

    # ── 斷線重連 ──────────────────────────────────────────

    def start_reconnect_monitor(self) -> None:
        """啟動背景重連監控執行緒。"""
        if self._reconnect_thread is not None and self._reconnect_thread.is_alive():
            return

        self._stop_reconnect.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, daemon=True, name="sinopac-reconnect"
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        """背景重連迴圈。"""
        attempts = 0
        while not self._stop_reconnect.is_set():
            if self._connected:
                attempts = 0
                self._stop_reconnect.wait(self._config.reconnect_interval)
                continue

            if attempts >= self._config.max_reconnect_attempts:
                logger.error("Max reconnect attempts reached (%d)", attempts)
                break

            attempts += 1
            logger.warning("Connection lost, reconnecting (attempt %d)...", attempts)

            try:
                success = self.connect()
                if success:
                    logger.info("Reconnected successfully")
                    attempts = 0
            except Exception:
                logger.exception("Reconnect attempt %d failed", attempts)

            # Exponential backoff (capped at 60s)
            wait = min(self._config.reconnect_interval * (2 ** (attempts - 1)), 60.0)
            self._stop_reconnect.wait(wait)

    # ── 內部工具 ──────────────────────────────────────────

    def _ensure_connected(self) -> None:
        if not self._connected or self._api is None:
            raise ConnectionError("Not connected to Shioaji. Call connect() first.")

    def _resolve_contract(self, symbol: str) -> Any:
        """從 Shioaji 取得合約物件。"""
        try:
            # 移除 .TW/.TWO suffix（本系統用 Yahoo 格式，Shioaji 用純代碼）
            code = symbol.replace(".TW", "").replace(".TWO", "")
            # 台股代碼（純數字或數字+英文）
            contract = self._api.Contracts.Stocks.get(code, None)
            if contract is None:
                # 嘗試期貨
                contract = self._api.Contracts.Futures.get(symbol, None)
            return contract
        except Exception:
            logger.debug("Contract resolution failed: %s", symbol, exc_info=True)
            return None

    def _map_price_type(self, order: Order) -> Any:
        """Order → Shioaji 價格類型。"""
        import shioaji as sj

        if order.order_type == OrderType.MARKET:
            return sj.constant.StockPriceType.MKT
        return sj.constant.StockPriceType.LMT

    def _shares_to_lots(self, shares: Decimal, symbol: str) -> tuple[int, bool]:
        """股數 → (數量, 是否零股)。

        台股 1000 股 = 1 張。若 < 1000 股為零股，回傳 (股數, True)。
        整股回傳 (張數, False)。
        """
        lot_size = 1000
        int_shares = int(shares)
        if int_shares < lot_size:
            return (int_shares, True)  # 零股：數量為股數
        lots = int_shares // lot_size
        return (lots, False)  # 整股：數量為張數

    @property
    def simulation(self) -> bool:
        return self._config.simulation

    @property
    def api(self) -> Any:
        """直接存取底層 Shioaji API（進階用途）。"""
        return self._api
