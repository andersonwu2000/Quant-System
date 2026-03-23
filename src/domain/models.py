"""
領域模型 — 整個系統的核心型別定義。

設計原則：
- 用 Decimal 處理所有金額和價格，杜絕浮點誤差
- frozen dataclass 用於不可變值物件
- 普通 dataclass 用於可變聚合根
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


# ─── 枚舉 ───────────────────────────────────────────────

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class AssetClass(Enum):
    EQUITY = "EQUITY"
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


# ─── 值物件 (不可變) ────────────────────────────────────

@dataclass(frozen=True)
class Instrument:
    """金融工具的靜態描述。"""
    symbol: str                             # "2330.TW", "AAPL"
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    currency: str = "TWD"
    lot_size: int = 1                       # 最小交易單位 (台股=1000)
    tick_size: Decimal = Decimal("0.01")
    multiplier: Decimal = Decimal("1")      # 期貨/選擇權合約乘數


@dataclass(frozen=True)
class Bar:
    """一根 K 線。"""
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    freq: str = "1d"                        # "1m", "5m", "1d"


# ─── 聚合根 (可變) ─────────────────────────────────────

@dataclass
class Position:
    """單一標的的持倉。"""
    instrument: Instrument
    quantity: Decimal                        # 正=多頭, 負=空頭
    avg_cost: Decimal
    market_price: Decimal = Decimal("0")

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.market_price * self.instrument.multiplier

    @property
    def unrealized_pnl(self) -> Decimal:
        return (
            (self.market_price - self.avg_cost)
            * self.quantity
            * self.instrument.multiplier
        )



@dataclass
class Order:
    """訂單。"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    instrument: Instrument = field(default_factory=lambda: Instrument(""))
    side: Side = Side.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Decimal("0")
    price: Decimal | None = None            # None = 市價單
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: Decimal = Decimal("0")
    filled_avg_price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str = ""
    client_order_id: str = ""
    reject_reason: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )

    @property
    def notional(self) -> Decimal:
        """訂單名義金額。"""
        px = self.price or Decimal("0")  # market orders: notional unknown without market price
        return self.quantity * px * self.instrument.multiplier


@dataclass
class Portfolio:
    """投資組合 — 持倉 + 現金。"""
    positions: dict[str, Position] = field(default_factory=dict)  # key=symbol
    cash: Decimal = Decimal("1000000")
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    initial_cash: Decimal = Decimal("1000000")
    nav_sod: Decimal = Decimal("0")  # start-of-day NAV（回測引擎更新）

    @property
    def nav(self) -> Decimal:
        mv = sum(p.market_value for p in self.positions.values())
        return self.cash + mv

    @property
    def gross_exposure(self) -> Decimal:
        return sum((abs(p.market_value) for p in self.positions.values()), Decimal(0))

    @property
    def net_exposure(self) -> Decimal:
        return sum((p.market_value for p in self.positions.values()), Decimal(0))

    @property
    def daily_pnl(self) -> Decimal:
        if self.nav_sod == 0:
            return Decimal("0")
        return self.nav - self.nav_sod

    @property
    def daily_drawdown(self) -> Decimal:
        if self.nav_sod == 0:
            return Decimal("0")
        return -self.daily_pnl / self.nav_sod

    def get_position_weight(self, symbol: str) -> Decimal:
        if symbol not in self.positions or self.nav == 0:
            return Decimal("0")
        return self.positions[symbol].market_value / self.nav

    def update_market_prices(self, prices: dict[str, Decimal]) -> None:
        """用最新市價更新所有持倉。"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].market_price = price


# ─── 風控相關 ──────────────────────────────────────────

@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str = ""
    modified_qty: Decimal | None = None     # 風控縮量時使用

    @staticmethod
    def APPROVE() -> RiskDecision:
        return RiskDecision(approved=True)

    @staticmethod
    def REJECT(reason: str) -> RiskDecision:
        return RiskDecision(approved=False, reason=reason)

    @staticmethod
    def MODIFY(new_qty: Decimal, reason: str) -> RiskDecision:
        return RiskDecision(approved=True, reason=reason, modified_qty=new_qty)


@dataclass(frozen=True)
class RiskAlert:
    """風控告警事件。"""
    timestamp: datetime
    rule_name: str
    severity: Severity
    metric_value: float
    threshold: float
    action_taken: str
    message: str = ""


# ─── 回測相關 ──────────────────────────────────────────

@dataclass
class Trade:
    """一筆成交記錄。"""
    timestamp: datetime
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage_bps: Decimal
    strategy_id: str = ""
    order_id: str = ""
    signal_value: float | None = None
