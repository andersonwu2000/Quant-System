"""
領域模型 — 整個系統的核心型別定義。

設計原則：
- 用 Decimal 處理所有金額和價格，杜絕浮點誤差
- frozen dataclass 用於不可變值物件
- 普通 dataclass 用於可變聚合根
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum


# ─── 交易不變量異常 ────────────────────────────────────


class TradingInvariantError(Exception):
    """交易路徑中的不變量被違反。

    捕獲後：
    1. 停止所有交易（set kill_switch_fired = True）
    2. 發送 P0 通知
    3. 記錄完整 context 到 audit log
    不靜默吞掉。不自動恢復。必須人工確認後才能重啟。
    """
    pass


# ─── 枚舉 ───────────────────────────────────────────────

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class AssetClass(Enum):
    EQUITY = "EQUITY"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    ETF = "ETF"


class Market(Enum):
    TW = "tw"
    US = "us"


class SubClass(Enum):
    """資產子類別 — 細分 ETF 暴露的底層資產。"""
    STOCK = "stock"
    ETF_EQUITY = "etf_equity"
    ETF_BOND = "etf_bond"
    ETF_COMMODITY = "etf_commodity"
    ETF_MIXED = "etf_mixed"
    FUTURE = "future"


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


class OrderCondition(Enum):
    CASH = "CASH"                     # 現股
    MARGIN_TRADING = "MARGIN_TRADING"  # 融資
    SHORT_SELLING = "SHORT_SELLING"   # 融券
    DAY_TRADE = "DAY_TRADE"          # 現股當沖


class StockOrderLot(Enum):
    COMMON = "COMMON"                 # 整股
    INTRADAY_ODD = "INTRADAY_ODD"    # 盤中零股
    ODD = "ODD"                       # 盤後零股
    FIXING = "FIXING"                 # 定盤


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


# ─── 值物件 (不可變) ────────────────────────────────────

@dataclass(frozen=True)
class Instrument:
    """
    金融工具的靜態描述 — 統一模型，覆蓋股票/ETF/期貨。

    所有可交易標的共用此模型。InstrumentRegistry 使用相同的 class。
    """
    symbol: str                             # "2330.TW", "AAPL", "ES=F", "TLT"
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    sub_class: SubClass = SubClass.STOCK
    market: Market = Market.US
    currency: str = "TWD"
    lot_size: int = 1                       # 最小交易單位 (台股=1000)
    tick_size: Decimal = Decimal("0.01")
    multiplier: Decimal = Decimal("1")      # 期貨合約乘數
    margin_rate: Decimal | None = None      # 保證金比率（期貨）
    commission_rate: Decimal = Decimal("0")  # per-instrument 手續費率 (0=使用 SimConfig)
    tax_rate: Decimal = Decimal("0")        # per-instrument 稅率 (0=使用 SimConfig)
    sector: str = ""


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
    order_cond: OrderCondition = OrderCondition.CASH
    order_lot: StockOrderLot = StockOrderLot.COMMON

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
    """投資組合 — 持倉 + 現金。

    Thread safety: use `lock` for any mutation from non-asyncio threads
    (e.g. Shioaji tick callback). Asyncio code should use state.mutation_lock.
    """
    positions: dict[str, Position] = field(default_factory=dict)  # key=symbol
    cash: Decimal = Decimal("1000000")
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone(timedelta(hours=8))))  # UTC+8 台北
    initial_cash: Decimal = Decimal("1000000")
    nav_sod: Decimal = Decimal("0")  # start-of-day NAV（回測引擎更新）
    pending_settlements: list[tuple[str, Decimal]] = field(default_factory=list)  # (settle_date_str, amount)
    # Lock ordering (to prevent deadlocks):
    # 1. state.mutation_lock (asyncio.Lock) — acquired first for async routes
    # 2. portfolio.lock (threading.Lock) — acquired second for portfolio mutations
    # Never acquire portfolio.lock then mutation_lock (reverse order = deadlock risk)
    # Shioaji tick callback thread: only acquires portfolio.lock (no mutation_lock)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)  # #1: cross-thread safety

    def __deepcopy__(self, memo: dict[int, object]) -> "Portfolio":
        """Custom deepcopy that creates a new lock instead of copying the old one."""
        from copy import deepcopy
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "lock":
                object.__setattr__(result, k, threading.Lock())
            else:
                object.__setattr__(result, k, deepcopy(v, memo))
        return result

    @property
    def available_cash(self) -> Decimal:
        """Cash available for new orders.

        A-10 fix: apply_trades() already deducts cash immediately on BUY.
        pending_settlements tracks settlement dates but should NOT double-deduct.
        """
        return self.cash

    @property
    def nav(self) -> Decimal:
        """NAV（單幣別模式，向後相容）。混幣別時使用 nav_in_base()。"""
        mv = sum(p.market_value for p in self.positions.values())
        return self.cash + mv

    def nav_in_base(self, fx_rates: dict[tuple[str, str], Decimal] | None = None) -> Decimal:
        """
        以 base_currency 計價的 NAV。

        各持倉根據 instrument.currency 轉換。無 fx_rates 或單幣別時回退到 self.nav。
        """
        if not fx_rates:
            return self.nav

        base = self.base_currency
        total = self.total_cash(fx_rates)

        for pos in self.positions.values():
            cur = getattr(pos.instrument, "currency", base)
            if isinstance(cur, str):
                pos_cur = cur
            else:
                pos_cur = str(cur)
            mv = pos.market_value
            if pos_cur != base and (pos_cur, base) in fx_rates:
                mv = mv * fx_rates[(pos_cur, base)]
            total += mv

        return total

    @property
    def gross_exposure(self) -> Decimal:
        return sum((abs(p.market_value) for p in self.positions.values()), Decimal(0))

    @property
    def net_exposure(self) -> Decimal:
        return sum((p.market_value for p in self.positions.values()), Decimal(0))

    @property
    def daily_pnl(self) -> Decimal:
        sod = self.nav_sod if self.nav_sod > 0 else self.nav
        return self.nav - sod

    @property
    def daily_drawdown(self) -> Decimal:
        sod = self.nav_sod if self.nav_sod > 0 else self.nav
        if sod == 0:
            return Decimal("0")
        return -self.daily_pnl / sod

    def get_position_weight(self, symbol: str) -> Decimal:
        if symbol not in self.positions or self.nav == 0:
            return Decimal("0")
        return self.positions[symbol].market_value / self.nav

    # ── 多幣別擴展（向後相容） ──────────────────────────

    # 多幣別現金帳戶：key=幣別字串 ("TWD", "USD"), value=金額
    # 預設為空。若為空，則所有操作回退到使用 self.cash (單幣別)。
    cash_by_currency: dict[str, Decimal] = field(default_factory=dict)
    base_currency: str = "TWD"

    def total_cash(self, fx_rates: dict[tuple[str, str], Decimal] | None = None) -> Decimal:
        """以 base_currency 計算總現金。無多幣別帳戶時直接回傳 self.cash。"""
        if not self.cash_by_currency:
            return self.cash
        total = Decimal("0")
        for cur, amount in self.cash_by_currency.items():
            if cur == self.base_currency:
                total += amount
            elif fx_rates and (cur, self.base_currency) in fx_rates:
                total += amount * fx_rates[(cur, self.base_currency)]
            else:
                total += amount  # 無匯率時假設 1:1
        return total

    def currency_exposure(self) -> dict[str, Decimal]:
        """各幣別的淨暴露（現金 + 持倉市值）。"""
        exposure: dict[str, Decimal] = {}
        # 現金
        if self.cash_by_currency:
            for cur, amount in self.cash_by_currency.items():
                exposure[cur] = exposure.get(cur, Decimal("0")) + amount
        else:
            exposure[self.base_currency] = self.cash
        # 持倉 — 使用 instrument.currency
        for pos in self.positions.values():
            cur = getattr(pos.instrument, "currency", self.base_currency)
            if isinstance(cur, str):
                pass
            else:
                cur = str(cur)
            exposure[cur] = exposure.get(cur, Decimal("0")) + pos.market_value
        return exposure

    def asset_class_weights(self) -> dict[str, Decimal]:
        """各資產類別佔 NAV 的權重。"""
        nav_val = self.nav
        if nav_val == 0:
            return {}
        weights: dict[str, Decimal] = {}
        for pos in self.positions.values():
            ac = pos.instrument.asset_class.value
            weights[ac] = weights.get(ac, Decimal("0")) + abs(pos.market_value) / nav_val
        return weights

    def update_market_prices(self, prices: dict[str, Decimal]) -> None:
        """用最新市價更新所有持倉。Thread-safe via self.lock。"""
        with self.lock:
            for symbol, price in prices.items():
                if symbol in self.positions:
                    self.positions[symbol].market_price = price

    def _check_invariants(self) -> None:
        """交易後自動執行。違反任一條即 raise TradingInvariantError。"""
        import logging as _logging
        _logger = _logging.getLogger(__name__)

        # I1: NAV 永遠非負
        if self.nav < 0:
            raise TradingInvariantError(f"I1: NAV={self.nav} is negative")

        # I2: 現金永遠非負（不允許透支）
        if self.cash < 0:
            raise TradingInvariantError(f"I2: Cash={self.cash} is negative")

        # I3: 持倉數量必須 >= 0（做多策略不允許負持倉）
        for sym, pos in self.positions.items():
            if pos.quantity < 0:
                raise TradingInvariantError(f"I3: {sym} quantity={pos.quantity} is negative")

        # I4: NAV = cash + sum(market_value)，誤差 < 0.01% NAV or 100 TWD
        computed = self.cash + sum(p.market_value for p in self.positions.values())
        tolerance = max(self.nav * Decimal("0.0001"), Decimal("100"))
        if abs(computed - self.nav) > tolerance:
            raise TradingInvariantError(
                f"I4: NAV mismatch: computed={computed}, stored={self.nav}, tolerance={tolerance}")

        # I5: 單一持倉權重監控
        if self.nav > 0:
            for sym, pos in self.positions.items():
                weight = abs(pos.market_value) / self.nav
                if weight > Decimal("0.25"):
                    raise TradingInvariantError(
                        f"I5: {sym} weight={float(weight):.1%} > 25% hard limit")
                elif weight > Decimal("0.20"):
                    _logger.warning(
                        "I5: Position %s weight %.1f%% > 20%% — force rebalance next cycle",
                        sym, float(weight) * 100)


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
