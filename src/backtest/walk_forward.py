"""
Walk-Forward Analysis — 滑動視窗回測，評估策略的樣本外表現。

將時間序列切割為訓練/測試視窗，逐步向前滑動：
- 訓練視窗：尋找最佳參數（若提供 param_grid）
- 測試視窗：用訓練視窗的最佳參數（或預設參數）回測
- 匯總所有測試視窗的績效指標
"""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult
from src.backtest.engine import BacktestCancelled, BacktestConfig, BacktestEngine
from src.strategy.registry import resolve_strategy

logger = logging.getLogger(__name__)


@dataclass
class WFAConfig:
    """Walk-Forward Analysis 配置。"""
    train_days: int
    test_days: int
    step_days: int
    # BacktestConfig fields
    universe: list[str] = field(default_factory=list)
    initial_cash: float = 10_000_000.0
    freq: str = "1d"
    rebalance_freq: str = "daily"
    slippage_bps: float = 5.0
    commission_rate: float = 0.001425
    tax_rate: float = 0.003


@dataclass
class WFAFold:
    """單一 fold 的結果。"""
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_sharpe: float
    test_sharpe: float
    test_total_return: float
    best_params: dict[str, Any] | None = None


@dataclass
class WFAResult:
    """Walk-Forward Analysis 整體結果。"""
    folds: list[WFAFold]
    oos_total_return: float
    oos_sharpe: float
    oos_max_drawdown: float
    param_stability: dict[str, Any]


class WalkForwardAnalyzer:
    """Walk-Forward Analysis 執行器。"""

    def run(
        self,
        strategy_name: str,
        universe: list[str],
        start: str,
        end: str,
        config: WFAConfig,
        param_grid: dict[str, list[Any]] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> WFAResult:
        """執行 Walk-Forward Analysis。

        Args:
            strategy_name: 策略名稱（須在 registry 中）
            universe: 股票代碼清單
            start: 整體起始日期 (YYYY-MM-DD)
            end: 整體結束日期 (YYYY-MM-DD)
            config: WFA 配置
            param_grid: 參數網格搜尋（選用），格式 {"param": [v1, v2, ...]}

        Returns:
            WFAResult 包含所有 fold 結果及匯總指標

        Raises:
            ValueError: 日期範圍不足以形成至少一個 fold
        """
        # 生成 fold 日期
        folds_dates = self._generate_folds(start, end, config)
        if not folds_dates:
            min_days = config.train_days + config.test_days
            raise ValueError(
                f"Insufficient date range for walk-forward analysis. "
                f"Need at least {min_days} days, got "
                f"{(pd.Timestamp(end) - pd.Timestamp(start)).days} days."
            )

        logger.info(
            "WFA START: %d folds, strategy=%s, %s ~ %s",
            len(folds_dates), strategy_name, start, end,
        )

        folds: list[WFAFold] = []
        all_test_returns: list[float] = []
        all_test_sharpes: list[float] = []
        all_test_max_dds: list[float] = []
        all_best_params: list[dict[str, Any] | None] = []
        all_oos_daily: list[pd.Series] = []

        for i, (train_start, train_end, test_start, test_end) in enumerate(folds_dates):
            # 合作式取消：每個 fold 開始前檢查
            if cancel_event is not None and cancel_event.is_set():
                raise BacktestCancelled(
                    f"Walk-forward cancelled at fold {i}/{len(folds_dates)}"
                )

            logger.info(
                "WFA Fold %d: train=%s~%s, test=%s~%s",
                i, train_start, train_end, test_start, test_end,
            )

            best_params: dict[str, Any] | None = None
            train_sharpe = 0.0

            if param_grid:
                # Grid search on training set
                best_params, train_sharpe = self._grid_search(
                    strategy_name=strategy_name,
                    universe=universe,
                    start=train_start,
                    end=train_end,
                    config=config,
                    param_grid=param_grid,
                    cancel_event=cancel_event,
                )
            else:
                # Run training set with default params for train_sharpe
                train_result = self._run_backtest(
                    strategy_name=strategy_name,
                    universe=universe,
                    start=train_start,
                    end=train_end,
                    config=config,
                    params=None,
                    cancel_event=cancel_event,
                )
                train_sharpe = train_result.sharpe

            # Run test set with best params (or default)
            test_result = self._run_backtest(
                strategy_name=strategy_name,
                universe=universe,
                start=test_start,
                end=test_end,
                config=config,
                params=best_params,
                cancel_event=cancel_event,
            )

            fold = WFAFold(
                fold_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_sharpe=train_sharpe,
                test_sharpe=test_result.sharpe,
                test_total_return=test_result.total_return,
                best_params=best_params,
            )
            folds.append(fold)

            all_test_returns.append(test_result.total_return)
            all_test_sharpes.append(test_result.sharpe)
            all_test_max_dds.append(test_result.max_drawdown)
            all_best_params.append(best_params)
            if test_result.daily_returns is not None and len(test_result.daily_returns) > 0:
                all_oos_daily.append(test_result.daily_returns)

        # Aggregate OOS metrics
        # Compound total return across folds
        oos_total_return = float(
            np.prod([1 + r for r in all_test_returns]) - 1
        )
        # Concatenated OOS Sharpe (more accurate than per-fold mean)
        if all_oos_daily:
            concat_oos = pd.concat(all_oos_daily).dropna()
            concat_oos = concat_oos[~concat_oos.index.duplicated(keep='first')]
            oos_std = float(concat_oos.std()) if len(concat_oos) > 1 else 0.0
            oos_sharpe = float(concat_oos.mean() / oos_std * np.sqrt(252)) if oos_std > 0 else 0.0
        else:
            oos_sharpe = float(np.mean(all_test_sharpes)) if all_test_sharpes else 0.0
        oos_max_drawdown = float(max(all_test_max_dds)) if all_test_max_dds else 0.0

        # Parameter stability: track how params change across folds
        param_stability = self._compute_param_stability(all_best_params)

        result = WFAResult(
            folds=folds,
            oos_total_return=oos_total_return,
            oos_sharpe=oos_sharpe,
            oos_max_drawdown=oos_max_drawdown,
            param_stability=param_stability,
        )

        logger.info(
            "WFA DONE: %d folds, OOS return=%.2f%%, OOS sharpe=%.2f, OOS maxdd=%.2f%%",
            len(folds),
            oos_total_return * 100,
            oos_sharpe,
            oos_max_drawdown * 100,
        )

        return result

    def _generate_folds(
        self,
        start: str,
        end: str,
        config: WFAConfig,
    ) -> list[tuple[str, str, str, str]]:
        """生成 (train_start, train_end, test_start, test_end) 日期序列。"""
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)

        folds: list[tuple[str, str, str, str]] = []
        cursor = start_ts

        while True:
            train_start = cursor
            train_end = train_start + pd.tseries.offsets.BDay(config.train_days)
            test_start = train_end + pd.tseries.offsets.BDay(1)
            test_end = test_start + pd.tseries.offsets.BDay(config.test_days)

            if test_end > end_ts:
                break

            folds.append((
                train_start.strftime("%Y-%m-%d"),
                train_end.strftime("%Y-%m-%d"),
                test_start.strftime("%Y-%m-%d"),
                test_end.strftime("%Y-%m-%d"),
            ))

            cursor += pd.tseries.offsets.BDay(config.step_days)

        return folds

    def _run_backtest(
        self,
        strategy_name: str,
        universe: list[str],
        start: str,
        end: str,
        config: WFAConfig,
        params: dict[str, Any] | None,
        cancel_event: threading.Event | None = None,
    ) -> BacktestResult:
        """執行單次回測。"""
        strategy = resolve_strategy(strategy_name, params)
        bt_config = BacktestConfig(
            universe=universe,
            start=start,
            end=end,
            initial_cash=config.initial_cash,
            freq=config.freq,
            rebalance_freq=config.rebalance_freq,  # type: ignore[arg-type]
            slippage_bps=config.slippage_bps,
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
        )
        engine = BacktestEngine()
        return engine.run(strategy, bt_config, cancel_event=cancel_event)

    def _grid_search(
        self,
        strategy_name: str,
        universe: list[str],
        start: str,
        end: str,
        config: WFAConfig,
        param_grid: dict[str, list[Any]],
        cancel_event: threading.Event | None = None,
    ) -> tuple[dict[str, Any], float]:
        """在參數網格上搜尋最佳 Sharpe。

        Returns:
            (best_params, best_sharpe)
        """
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        best_sharpe = float("-inf")
        best_params: dict[str, Any] = {}

        for combo in combinations:
            params = dict(zip(keys, combo))
            try:
                result = self._run_backtest(
                    strategy_name=strategy_name,
                    universe=universe,
                    start=start,
                    end=end,
                    config=config,
                    params=params,
                    cancel_event=cancel_event,
                )
                if result.sharpe > best_sharpe:
                    best_sharpe = result.sharpe
                    best_params = params
            except Exception:
                logger.warning(
                    "Grid search failed for params %s, skipping", params,
                    exc_info=True,
                )
                continue

        if best_sharpe == float("-inf"):
            best_sharpe = 0.0

        return best_params, best_sharpe

    @staticmethod
    def _compute_param_stability(
        all_params: list[dict[str, Any] | None],
    ) -> dict[str, Any]:
        """計算參數穩定性指標。

        Returns:
            dict with param_name -> {values, unique_count} for each parameter.
        """
        non_none = [p for p in all_params if p is not None]
        if not non_none:
            return {}

        stability: dict[str, Any] = {}
        all_keys: set[str] = set()
        for p in non_none:
            all_keys.update(p.keys())

        for key in sorted(all_keys):
            values = [p.get(key) for p in non_none if key in p]
            try:
                numeric_values = [float(v) for v in values if v is not None]
                stability[key] = {
                    "values": values,
                    "unique_count": len(set(str(v) for v in values)),
                    "std": float(np.std(numeric_values)) if numeric_values else None,
                }
            except (TypeError, ValueError):
                stability[key] = {
                    "values": values,
                    "unique_count": len(set(str(v) for v in values)),
                    "std": None,
                }

        return stability
