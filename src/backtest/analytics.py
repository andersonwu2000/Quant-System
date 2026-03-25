"""
績效分析 — 從 NAV 序列計算所有績效指標。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.domain.models import Order, Trade
from src.portfolio.risk_model import RiskModel


# ── Deflated Sharpe Ratio (Bailey & López de Prado, 2014) ──────────

_EULER_MASCHERONI = 0.5772156649015329


def deflated_sharpe(
    observed_sharpe: float,
    n_trials: int,
    T: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio — probability that observed SR is not a false positive.

    Accounts for multiple testing (n_trials), non-normality (skewness, kurtosis),
    and sample length (T). All Sharpe ratio values are annualized (daily × √252).

    Based on Bailey & López de Prado (2014). Internally converts to
    per-observation scale for the E[max SR] computation.

    Args:
        observed_sharpe: The observed annualized Sharpe ratio.
        n_trials: Number of strategy trials / backtests conducted.
        T: Number of return observations (trading days).
        skewness: Skewness of returns (0 for normal).
        kurtosis: Kurtosis of returns (3 for normal).

    Returns:
        Probability (0 to 1) that the observed SR is not due to chance.
        DSR < 0.05 means likely overfit.
    """
    if T <= 1 or n_trials < 1:
        return 0.0

    N = max(n_trials, 1)

    # Convert annualized SR to per-observation SR for internal calculations
    sr = observed_sharpe / np.sqrt(252)

    # Expected maximum per-observation SR under the null (all strategies SR=0)
    # E[max SR] ≈ (1 - γ) × Φ⁻¹(1 - 1/N) + γ × Φ⁻¹(1 - 1/(N·e))
    # This gives the expected max of N i.i.d. standard normal draws,
    # scaled by SE of SR estimator (1/√T).
    if N == 1:
        e_max_sr = 0.0
    else:
        e_max_sr = float(
            (1.0 - _EULER_MASCHERONI) * norm.ppf(1.0 - 1.0 / N)
            + _EULER_MASCHERONI * norm.ppf(1.0 - 1.0 / (N * np.e))
        ) * (1.0 / np.sqrt(T))

    # Standard error of SR (accounting for non-normality)
    # Lo (2002): Var(SR) ≈ (1 + 0.5·SR² - skew·SR + (kurt-3)/4·SR²) / (T-1)
    se = float(np.sqrt(
        (1.0 + 0.5 * sr**2 - skewness * sr + (kurtosis - 3.0) / 4.0 * sr**2)
        / (T - 1)
    ))

    if se <= 0:
        return 0.0

    # DSR = Φ((observed_SR - E[max SR]) / SE)
    z = (sr - e_max_sr) / se
    return float(norm.cdf(z))


def min_backtest_length(
    n_trials: int,
    target_sharpe: float = 1.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    significance: float = 0.05,
) -> int:
    """Minimum Backtest Length — smallest T for SR to be statistically significant.

    Given N trials, find the minimum number of observations T such that
    DSR(observed=target_sharpe, N, T) >= (1 - significance).

    Args:
        n_trials: Number of strategy trials conducted.
        target_sharpe: The Sharpe ratio we want to validate.
        skewness: Skewness of returns.
        kurtosis: Kurtosis of returns.
        significance: Significance level (default 0.05).

    Returns:
        Minimum T (number of trading days).
    """
    if n_trials < 1 or target_sharpe <= 0:
        return 2

    threshold = 1.0 - significance

    # Binary search for T
    lo, hi = 2, 100000
    # First check if even hi is not enough
    if deflated_sharpe(target_sharpe, n_trials, hi, skewness, kurtosis) < threshold:
        return hi

    while lo < hi:
        mid = (lo + hi) // 2
        dsr = deflated_sharpe(target_sharpe, n_trials, mid, skewness, kurtosis)
        if dsr >= threshold:
            hi = mid
        else:
            lo = mid + 1

    return lo


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

    # ── VaR / CVaR ──
    var_95: float = 0.0               # 日 95% VaR
    cvar_95: float = 0.0              # 日 95% CVaR

    # ── Omega / Rolling Sharpe ──
    omega_ratio: float = 0.0           # Omega ratio (threshold=0)
    rolling_sharpe: list[float] = field(default_factory=list)  # 63-day rolling Sharpe

    # ── 拒絕訂單統計 ──
    rejected_orders: int = 0
    rejected_notional: float = 0.0

    # ── Deflated Sharpe Ratio ──
    deflated_sharpe_ratio: float = 0.0    # DSR (computed when n_trials provided)

    # ── 回測防禦警告 ──
    survivorship_warnings: list[str] = field(default_factory=list)
    price_warnings: list[str] = field(default_factory=list)

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
            f"VaR (95%):     {self.var_95:.4%}",
            f"CVaR (95%):    {self.cvar_95:.4%}",
            "",
            f"Total Trades:  {self.total_trades}",
            f"Win Rate:      {self.win_rate:.1%}",
            f"Total Comm.:   ${self.total_commission:,.0f}",
            f"Rejected Ord.: {self.rejected_orders}",
            f"Rejected Not.: ${self.rejected_notional:,.0f}",
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
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "rejected_orders": self.rejected_orders,
            "rejected_notional": self.rejected_notional,
            "omega_ratio": self.omega_ratio,
            "rolling_sharpe": self.rolling_sharpe,
            "deflated_sharpe_ratio": self.deflated_sharpe_ratio,
            "survivorship_warnings": self.survivorship_warnings,
            "price_warnings": self.price_warnings,
        }


def compute_omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
    """Omega ratio: Σ max(r - threshold, 0) / Σ max(threshold - r, 0).

    Returns inf if denominator is 0 (no losses), 0.0 if no data.
    """
    if returns.empty:
        return 0.0
    vals = np.asarray(returns.values, dtype=np.float64)
    gains = np.sum(np.maximum(vals - threshold, 0.0))
    losses = np.sum(np.maximum(threshold - vals, 0.0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def compute_rolling_sharpe(returns: pd.Series, window: int = 63) -> list[float]:
    """Rolling Sharpe ratio = rolling_mean / rolling_std * sqrt(252).

    Returns list of length max(0, len(returns) - window + 1).
    """
    if len(returns) < window:
        return []
    rolling_mean = returns.rolling(window).mean()
    rolling_std = returns.rolling(window).std()
    # rolling produces NaN for first (window-1) entries
    valid_mean = rolling_mean.iloc[window - 1:]
    valid_std = rolling_std.iloc[window - 1:]
    result: list[float] = []
    annualize = np.sqrt(252)
    for m, s in zip(valid_mean, valid_std):
        if s > 0:
            result.append(float(m / s * annualize))
        else:
            result.append(0.0)
    return result


def compute_analytics(
    nav_series: pd.Series,
    initial_cash: float,
    trades: list[Trade],
    strategy_name: str = "",
    config: object = None,
    rejected_orders: list[Order] | None = None,
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

    # Rejected order stats
    _rejected = rejected_orders or []
    n_rejected = len(_rejected)
    rejected_notional = sum(float(o.notional) for o in _rejected)

    # VaR / CVaR
    var_95 = RiskModel.compute_var(daily_returns, confidence=0.95, method="historical")
    cvar_95 = RiskModel.compute_cvar(daily_returns, confidence=0.95, method="historical")

    # 確定日期範圍
    start_date = str(nav_series.index[0].date()) if hasattr(nav_series.index[0], "date") else str(nav_series.index[0])
    end_date = str(nav_series.index[-1].date()) if hasattr(nav_series.index[-1], "date") else str(nav_series.index[-1])

    # Omega ratio & rolling Sharpe
    omega = compute_omega_ratio(daily_returns)
    rolling_sh = compute_rolling_sharpe(daily_returns)

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
        rejected_orders=n_rejected,
        rejected_notional=rejected_notional,
        var_95=var_95,
        cvar_95=cvar_95,
        omega_ratio=omega,
        rolling_sharpe=rolling_sh,
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
