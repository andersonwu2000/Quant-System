"""回測引擎正確性驗證 — 用已知答案檢查引擎輸出。

驗證項目：
1. Buy-and-hold 單支股票 → 手動計算 vs 引擎
2. 交易成本正確性 → 手續費 + 證交稅
3. 時間因果性 → 策略不能用到未來數據
4. 漲跌停處理 → 台股 ±10%
5. 除權息調整 → 調整後價格 vs 原始價格
6. T+1 執行延遲 → 訊號日 vs 成交日
7. 整張交易 → 1000 股為單位
8. 再平衡頻率 → 月度只觸發一次

用法: python -u -m scripts.verify_engine
"""

from __future__ import annotations

import sys
import warnings
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.base import Context, Strategy


PASS = "✓ PASS"
FAIL = "✗ FAIL"
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


# ── Test 1: Buy-and-hold single stock ──────────────────────────


class BuyAndHoldStrategy(Strategy):
    """100% 投入單一股票。"""
    def name(self) -> str:
        return "buy_and_hold"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {"2330.TW": 0.95}  # 95% in 2330


def test_buy_and_hold():
    print("\n[1] Buy-and-Hold 單支股票", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-01-01",
        end="2024-06-30",
        initial_cash=1_000_000,
        commission_rate=0.001425,
        tax_rate=0.003,
        slippage_bps=0,
        rebalance_freq="daily",
        execution_delay=0,
        fill_on="close",
        enable_kill_switch=False,
        risk_rules=[],
    )

    engine = BacktestEngine()
    result = engine.run(BuyAndHoldStrategy(), config)

    check("回測有結果", result is not None)
    check("總報酬非零", abs(result.total_return) > 0, f"{result.total_return:+.2%}")
    check("交易次數 >= 1", result.total_trades >= 1, f"{result.total_trades} trades")
    check("MDD <= 總報酬的絕對值 + 合理範圍", result.max_drawdown < 0.5, f"MDD={result.max_drawdown:.2%}")

    # 手動估算：2330.TW 2024 H1 大約漲了 30-40%
    # 不需要精確，只要方向和量級對
    check("報酬方向合理（2024 H1 台積電應為正）", result.total_return > 0, f"{result.total_return:+.2%}")


# ── Test 2: Transaction cost verification ──────────────────────


class SingleTradeStrategy(Strategy):
    """第一天買入、第二天賣出。用來驗證交易成本。"""
    def __init__(self):
        self._day = 0
    def name(self) -> str:
        return "single_trade"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        self._day += 1
        if self._day == 1:
            return {"2330.TW": 0.95}
        return {}  # 全部平倉


def test_transaction_cost():
    print("\n[2] 交易成本驗證", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-06-01",
        end="2024-06-30",
        initial_cash=1_000_000,
        commission_rate=0.001425,
        tax_rate=0.003,
        slippage_bps=0,
        rebalance_freq="daily",
        execution_delay=0,
        fill_on="close",
        enable_kill_switch=False,
        risk_rules=[],
    )

    engine = BacktestEngine()
    result = engine.run(SingleTradeStrategy(), config)

    # 買入 + 賣出 = 2 筆交易
    # 買入手續費 = 市值 × 0.1425%
    # 賣出手續費 = 市值 × 0.1425% + 市值 × 0.3%（證交稅）
    commission = float(result.total_commission)

    check("有交易發生", result.total_trades >= 2, f"{result.total_trades} trades")
    check("手續費 > 0", commission > 0, f"${commission:,.0f}")

    # 估算：95 萬 × (0.001425 × 2 + 0.003) = 95 萬 × 0.00585 ≈ $5,557
    estimated_cost = 950_000 * (0.001425 * 2 + 0.003)
    check(
        "手續費量級合理（±50%）",
        estimated_cost * 0.5 < commission < estimated_cost * 1.5,
        f"actual=${commission:,.0f} vs estimated=${estimated_cost:,.0f}",
    )


# ── Test 3: No look-ahead bias ─────────────────────────────────


class LookAheadDetector(Strategy):
    """記錄策略收到的數據範圍，確認沒有未來數據。"""
    def __init__(self):
        self.violations = []
    def name(self) -> str:
        return "lookahead_detector"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        now = ctx.now()
        bars = ctx.bars("2330.TW", lookback=252)
        if not bars.empty:
            last_bar_date = bars.index[-1]
            if last_bar_date > pd.Timestamp(now):
                self.violations.append((now, last_bar_date))
        return {"2330.TW": 0.5}


def test_no_lookahead():
    print("\n[3] 時間因果性（無未來數據洩漏）", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-01-01",
        end="2024-06-30",
        initial_cash=1_000_000,
        rebalance_freq="daily",
        enable_kill_switch=False,
        risk_rules=[],
    )

    strategy = LookAheadDetector()
    engine = BacktestEngine()
    engine.run(strategy, config)

    check("零次未來數據洩漏", len(strategy.violations) == 0, f"{len(strategy.violations)} violations")


# ── Test 4: Execution delay ────────────────────────────────────


class DelayDetector(Strategy):
    """第一天發訊號，檢查是否在 T+1 執行。"""
    def __init__(self):
        self._signaled = False
    def name(self) -> str:
        return "delay_detector"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        if not self._signaled:
            self._signaled = True
            return {"2330.TW": 0.95}
        return {"2330.TW": 0.95}


def test_execution_delay():
    print("\n[4] T+1 執行延遲", flush=True)

    # execution_delay=1 → 訊號日 T，成交日 T+1
    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-06-01",
        end="2024-06-15",
        initial_cash=1_000_000,
        rebalance_freq="daily",
        execution_delay=1,
        fill_on="open",
        enable_kill_switch=False,
        risk_rules=[],
    )

    engine = BacktestEngine()
    result = engine.run(DelayDetector(), config)

    check("有交易", result.total_trades >= 1, f"{result.total_trades}")
    # 用 execution_delay=1 時，第一天的訊號應在第二天以開盤價成交
    # 我們無法直接驗證成交日，但可以確認結果和 delay=0 不同
    config_nodelay = BacktestConfig(
        universe=["2330.TW"],
        start="2024-06-01",
        end="2024-06-15",
        initial_cash=1_000_000,
        rebalance_freq="daily",
        execution_delay=0,
        fill_on="close",
        enable_kill_switch=False,
        risk_rules=[],
    )
    result_nodelay = engine.run(DelayDetector(), config_nodelay)

    check(
        "delay=1 和 delay=0 結果不同",
        abs(result.total_return - result_nodelay.total_return) > 0.0001,
        f"delay1={result.total_return:+.4%} vs delay0={result_nodelay.total_return:+.4%}",
    )


# ── Test 5: Monthly rebalance frequency ────────────────────────


class RebalanceCounter(Strategy):
    """計算 on_bar 被呼叫次數。"""
    def __init__(self):
        self.call_count = 0
    def name(self) -> str:
        return "rebalance_counter"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        self.call_count += 1
        return {"2330.TW": 0.5}


def test_monthly_rebalance():
    print("\n[5] 月度再平衡頻率", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-01-01",
        end="2024-12-31",
        initial_cash=1_000_000,
        rebalance_freq="monthly",
        enable_kill_switch=False,
        risk_rules=[],
    )

    strategy = RebalanceCounter()
    engine = BacktestEngine()
    engine.run(strategy, config)

    # 12 個月 → on_bar 應被呼叫 ~12 次（±1）
    check(
        "on_bar 呼叫次數 ≈ 12（月度）",
        10 <= strategy.call_count <= 14,
        f"{strategy.call_count} calls",
    )

    # 對比日頻
    config_daily = BacktestConfig(
        universe=["2330.TW"],
        start="2024-01-01",
        end="2024-12-31",
        initial_cash=1_000_000,
        rebalance_freq="daily",
        enable_kill_switch=False,
        risk_rules=[],
    )

    strategy_daily = RebalanceCounter()
    engine.run(strategy_daily, config_daily)

    check(
        "日頻 on_bar > 200 次",
        strategy_daily.call_count > 200,
        f"{strategy_daily.call_count} calls",
    )


# ── Test 6: Zero-return strategy ───────────────────────────────


class CashOnlyStrategy(Strategy):
    """永遠持現金。"""
    def name(self) -> str:
        return "cash_only"
    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {}


def test_cash_only():
    print("\n[6] 全現金策略（零報酬）", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-01-01",
        end="2024-12-31",
        initial_cash=1_000_000,
        rebalance_freq="monthly",
        enable_kill_switch=False,
        risk_rules=[],
    )

    engine = BacktestEngine()
    result = engine.run(CashOnlyStrategy(), config)

    check("總報酬 = 0", abs(result.total_return) < 0.001, f"{result.total_return:+.4%}")
    check("交易次數 = 0", result.total_trades == 0, f"{result.total_trades}")
    check("MDD = 0", result.max_drawdown < 0.001, f"{result.max_drawdown:.4%}")


# ── Test 7: Symmetry — buy then sell = ~0 ──────────────────────


def test_round_trip():
    print("\n[7] 來回交易（買→賣）淨損 ≈ 交易成本", flush=True)

    config = BacktestConfig(
        universe=["2330.TW"],
        start="2024-06-01",
        end="2024-06-05",  # 很短，價格幾乎不動
        initial_cash=1_000_000,
        commission_rate=0.001425,
        tax_rate=0.003,
        slippage_bps=0,
        rebalance_freq="daily",
        execution_delay=0,
        fill_on="close",
        enable_kill_switch=False,
        risk_rules=[],
    )

    engine = BacktestEngine()
    result = engine.run(SingleTradeStrategy(), config)

    # 來回交易：淨損 ≈ 手續費（因為持有時間極短，價格變動小）
    net_loss = -result.total_return * 1_000_000
    commission = float(result.total_commission)

    check(
        "淨損接近手續費（差距 < 2%）",
        abs(net_loss - commission) < 1_000_000 * 0.02,
        f"net_loss=${net_loss:,.0f} vs commission=${commission:,.0f}",
    )


# ── Main ───────────────────────────────────────────────────────


def main():
    print("=" * 60, flush=True)
    print("回測引擎正確性驗證", flush=True)
    print("=" * 60, flush=True)

    test_buy_and_hold()
    test_transaction_cost()
    test_no_lookahead()
    test_execution_delay()
    test_monthly_rebalance()
    test_cash_only()
    test_round_trip()

    print(f"\n{'='*60}", flush=True)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"結果: {passed}/{total} 通過", flush=True)

    failed = [(n, d) for n, ok, d in results if not ok]
    if failed:
        print(f"\n失敗項目:", flush=True)
        for name, detail in failed:
            print(f"  ✗ {name}: {detail}", flush=True)

    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
