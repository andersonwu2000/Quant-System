"""
績效分析 — 從 NAV 序列計算所有績效指標。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.domain.models import Trade


@dataclass
class BacktestResult:
    """回測結果。"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float

    # ── 收益指標 ──
    total_return: float             # 總報酬率
    annual_return: float            # 年化報酬率
    sharpe: float                   # Sharpe Ratio (無風險利率=0)
    sortino: float                  # Sortino Ratio
    calmar: float                   # Calmar Ratio (年化報酬/最大回撤)

    # ── 風險指標 ──
    max_drawdown: float             # 最大回撤 (正數)
    max_drawdown_duration: int      # 最大回撤持續天數
    volatility: float               # 年化波動率
    downside_vol: float             # 下行波動率

    # ── 交易統計 ──
    total_trades: int
    win_rate: float
    avg_trade_return: float
    total_commission: float
    turnover: float                 # 平均換手率

    # ── 時序數據 ──
    nav_series: pd.Series = field(repr=False, default_factory=pd.Series)
    daily_returns: pd.Series = field(repr=False, default_factory=pd.Series)
    drawdown_series: pd.Series = field(repr=False, default_factory=pd.Series)
    trades: list[Trade] = field(repr=False, default_factory=list)

    def summary(self) -> str:
        """文字摘要。"""
        lines = [
            f"═══ {self.strategy_name} Backtest Result ═══",
            f"Period:        {self.start_date} ~ {self.end_date}",
            f"Initial Cash:  ${self.initial_cash:,.0f}",
            f"Final NAV:     ${self.nav_series.iloc[-1]:,.0f}" if len(self.nav_series) > 0 else "",
            "",
            f"Total Return:  {self.total_return:+.2%}",
            f"Annual Return: {self.annual_return:+.2%}",
            f"Volatility:    {self.volatility:.2%}",
            f"Sharpe Ratio:  {self.sharpe:.2f}",
            f"Sortino Ratio: {self.sortino:.2f}",
            f"Calmar Ratio:  {self.calmar:.2f}",
            "",
            f"Max Drawdown:  {self.max_drawdown:.2%}",
            f"Max DD Days:   {self.max_drawdown_duration}",
            "",
            f"Total Trades:  {self.total_trades}",
            f"Win Rate:      {self.win_rate:.1%}",
            f"Total Comm.:   ${self.total_commission:,.0f}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """轉為 dict（用於 API 回應和 DB 存儲）。"""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "calmar": self.calmar,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": self.volatility,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_commission": self.total_commission,
        }


def compute_analytics(
    nav_series: pd.Series,
    initial_cash: float,
    trades: list[Trade],
    strategy_name: str = "",
    config: object = None,
) -> BacktestResult:
    """從 NAV 序列計算完整績效指標。"""
    if nav_series.empty:
        return _empty_result(strategy_name, initial_cash)

    # 日收益率
    daily_returns = nav_series.pct_change().dropna()

    # 總報酬
    total_return = float(nav_series.iloc[-1] / initial_cash - 1)

    # 年化報酬 (假設 252 交易日)
    n_days = len(nav_series)
    n_years = n_days / 252
    annual_return = float((1 + total_return) ** (1 / max(n_years, 0.01)) - 1) if total_return > -1 else -1.0

    # 年化波動率
    volatility = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0

    # 下行波動率
    negative_returns = daily_returns[daily_returns < 0]
    downside_vol = float(negative_returns.std() * np.sqrt(252)) if len(negative_returns) > 1 else 0.0

    # Sharpe Ratio
    sharpe = annual_return / volatility if volatility > 0 else 0.0

    # Sortino Ratio
    sortino = annual_return / downside_vol if downside_vol > 0 else 0.0

    # 回撤
    cummax = nav_series.cummax()
    drawdown = (nav_series - cummax) / cummax
    max_drawdown = float(abs(drawdown.min()))

    # Calmar Ratio
    calmar = annual_return / max_drawdown if max_drawdown > 0 else 0.0

    # 最大回撤持續天數
    dd_duration = _max_drawdown_duration(drawdown)

    # 交易統計
    total_trades = len(trades)
    total_commission = sum(float(t.commission) for t in trades)

    # 勝率（簡化計算：基於每筆交易的 PnL 符號）
    win_rate, avg_trade_return = _trade_stats(trades)

    # 換手率
    turnover = _estimate_turnover(trades, initial_cash, n_days)

    # 確定日期範圍
    start_date = str(nav_series.index[0].date()) if hasattr(nav_series.index[0], "date") else str(nav_series.index[0])
    end_date = str(nav_series.index[-1].date()) if hasattr(nav_series.index[-1], "date") else str(nav_series.index[-1])

    return BacktestResult(
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        total_return=total_return,
        annual_return=annual_return,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        max_drawdown_duration=dd_duration,
        volatility=volatility,
        downside_vol=downside_vol,
        total_trades=total_trades,
        win_rate=win_rate,
        avg_trade_return=avg_trade_return,
        total_commission=total_commission,
        turnover=turnover,
        nav_series=nav_series,
        daily_returns=daily_returns,
        drawdown_series=drawdown,
        trades=trades,
    )


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    """計算最長回撤持續天數。"""
    if drawdown.empty:
        return 0
    in_dd = drawdown < 0
    if not in_dd.any():
        return 0

    groups = (~in_dd).cumsum()
    dd_groups = groups[in_dd]
    if dd_groups.empty:
        return 0
    return int(dd_groups.value_counts().max())


def _trade_stats(trades: list[Trade]) -> tuple[float, float]:
    """計算勝率和平均交易收益。"""
    if not trades:
        return 0.0, 0.0

    # 簡化：按 symbol 配對 BUY/SELL 計算 PnL
    # 這裡用簡單的方式：假設所有 BUY 後都有 SELL
    pnls: list[float] = []
    open_positions: dict[str, list[float]] = {}

    for t in trades:
        symbol = t.symbol
        if t.side.value == "BUY":
            open_positions.setdefault(symbol, []).append(float(t.price))
        elif t.side.value == "SELL" and symbol in open_positions and open_positions[symbol]:
            buy_price = open_positions[symbol].pop(0)
            pnl = (float(t.price) - buy_price) * float(t.quantity)
            pnls.append(pnl)

    if not pnls:
        return 0.0, 0.0

    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls)
    avg_return = sum(pnls) / len(pnls)
    return win_rate, avg_return


def _estimate_turnover(trades: list[Trade], nav: float, n_days: int) -> float:
    """估算年化換手率。"""
    if not trades or nav <= 0 or n_days <= 0:
        return 0.0
    total_traded = sum(float(t.quantity * t.price) for t in trades)
    daily_turnover = total_traded / nav / n_days
    return daily_turnover * 252


def _empty_result(name: str, cash: float) -> BacktestResult:
    return BacktestResult(
        strategy_name=name,
        start_date="",
        end_date="",
        initial_cash=cash,
        total_return=0,
        annual_return=0,
        sharpe=0,
        sortino=0,
        calmar=0,
        max_drawdown=0,
        max_drawdown_duration=0,
        volatility=0,
        downside_vol=0,
        total_trades=0,
        win_rate=0,
        avg_trade_return=0,
        total_commission=0,
        turnover=0,
    )
