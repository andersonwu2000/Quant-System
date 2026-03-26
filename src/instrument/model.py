"""
金融工具模型 — 從 src.domain.models 重新匯出。

統一後的 Instrument 定義在 src/domain/models.py，此檔提供：
1. 向後相容的 re-export（既有 import 不需改）
2. 預設交易成本模板（各市場的預設值）
3. Currency enum（domain/models.py 用 str，此處提供 enum 便利）
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

# ── 從 domain 重新匯出（統一模型） ──────────────────────

from src.core.models import AssetClass, Instrument, Market, SubClass

__all__ = [
    "AssetClass",
    "Currency",
    "Instrument",
    "Market",
    "SubClass",
    "TW_STOCK_DEFAULTS",
    "US_STOCK_DEFAULTS",
    "TW_FUTURES_DEFAULTS",
    "US_FUTURES_DEFAULTS",
]


class Currency(Enum):
    """幣別 enum（便利用途，domain/models.py 中 currency 為 str）。"""

    TWD = "TWD"
    USD = "USD"


# ── 預設交易成本模板 ─────────────────────────────────────

TW_STOCK_DEFAULTS = dict(
    market=Market.TW,
    currency="TWD",
    lot_size=1000,
    commission_rate=Decimal("0.001425"),
    tax_rate=Decimal("0.003"),
)

US_STOCK_DEFAULTS = dict(
    market=Market.US,
    currency="USD",
    lot_size=1,
    commission_rate=Decimal("0"),
    tax_rate=Decimal("0"),
)

TW_FUTURES_DEFAULTS = dict(
    asset_class=AssetClass.FUTURE,
    sub_class=SubClass.FUTURE,
    market=Market.TW,
    currency="TWD",
    lot_size=1,
    margin_rate=Decimal("0.10"),
    commission_rate=Decimal("0.00002"),
    tax_rate=Decimal("0.00002"),
)

US_FUTURES_DEFAULTS = dict(
    asset_class=AssetClass.FUTURE,
    sub_class=SubClass.FUTURE,
    market=Market.US,
    currency="USD",
    lot_size=1,
    commission_rate=Decimal("0"),
    tax_rate=Decimal("0"),
)
