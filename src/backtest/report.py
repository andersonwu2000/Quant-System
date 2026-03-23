"""
回測報告生成器 — HTML 報告、基準比較、CSV 匯出。
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult

logger = logging.getLogger(__name__)


def export_trades_csv(result: BacktestResult, path: str | Path) -> Path:
    """匯出交易明細為 CSV 檔案。"""
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "symbol", "side", "quantity", "price",
            "commission", "slippage_bps", "strategy_id", "order_id",
        ])
        for t in result.trades:
            writer.writerow([
                str(t.timestamp),
                t.symbol,
                t.side.value,
                str(t.quantity),
                str(t.price),
                str(t.commission),
                str(t.slippage_bps),
                t.strategy_id,
                t.order_id,
            ])
    logger.info("Exported %d trades to %s", len(result.trades), path)
    return path


def export_nav_csv(result: BacktestResult, path: str | Path) -> Path:
    """匯出每日 NAV 為 CSV 檔案。"""
    path = Path(path)
    nav_df = result.nav_series.reset_index()
    nav_df.columns = ["date", "nav"]
    nav_df["date"] = nav_df["date"].astype(str)
    nav_df.to_csv(path, index=False, encoding="utf-8")
    logger.info("Exported NAV series (%d days) to %s", len(nav_df), path)
    return path


def compare_with_benchmark(
    result: BacktestResult,
    benchmark_nav: pd.Series,
    benchmark_name: str = "Benchmark",
) -> dict[str, Any]:
    """
    與基準指數比較。

    Args:
        result: 回測結果
        benchmark_nav: 基準指數 NAV 序列（DatetimeIndex）
        benchmark_name: 基準名稱

    Returns:
        比較結果字典
    """
    strat_nav = result.nav_series
    # 對齊日期
    common = strat_nav.index.intersection(benchmark_nav.index)
    if len(common) < 2:
        return {"error": "Not enough overlapping dates"}

    s = strat_nav.loc[common]
    b = benchmark_nav.loc[common]

    # 正規化至起始 = 1.0
    s_norm = s / s.iloc[0]
    b_norm = b / b.iloc[0]

    s_ret = s_norm.pct_change().dropna()
    b_ret = b_norm.pct_change().dropna()

    n_years = len(common) / 252

    # 策略指標
    strat_total = float(s_norm.iloc[-1] - 1)
    strat_annual = float((1 + strat_total) ** (1 / max(n_years, 0.01)) - 1)
    strat_vol = float(s_ret.std() * np.sqrt(252))

    # 基準指標
    bench_total = float(b_norm.iloc[-1] - 1)
    bench_annual = float((1 + bench_total) ** (1 / max(n_years, 0.01)) - 1)
    bench_vol = float(b_ret.std() * np.sqrt(252))

    # 超額報酬
    excess_return = strat_annual - bench_annual

    # Tracking Error
    tracking = s_ret - b_ret
    tracking_error = float(tracking.std() * np.sqrt(252))

    # Information Ratio
    ir = excess_return / tracking_error if tracking_error > 0 else 0.0

    # Beta 與 Alpha
    cov = np.cov(s_ret, b_ret)
    beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 1.0
    alpha = strat_annual - beta * bench_annual

    # 最大回撤比較
    s_dd = (s_norm / s_norm.cummax() - 1).min()
    b_dd = (b_norm / b_norm.cummax() - 1).min()

    return {
        "benchmark_name": benchmark_name,
        "strategy": {
            "total_return": strat_total,
            "annual_return": strat_annual,
            "volatility": strat_vol,
            "max_drawdown": abs(float(s_dd)),
            "sharpe": strat_annual / strat_vol if strat_vol > 0 else 0,
        },
        "benchmark": {
            "total_return": bench_total,
            "annual_return": bench_annual,
            "volatility": bench_vol,
            "max_drawdown": abs(float(b_dd)),
            "sharpe": bench_annual / bench_vol if bench_vol > 0 else 0,
        },
        "relative": {
            "excess_return": excess_return,
            "tracking_error": tracking_error,
            "information_ratio": ir,
            "beta": beta,
            "alpha": alpha,
        },
    }


def generate_html_report(
    result: BacktestResult,
    benchmark_comparison: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> str:
    """
    生成 HTML 回測報告。

    包含：績效摘要、NAV 曲線圖、回撤圖、交易統計。
    使用內嵌 Chart.js CDN 繪圖。

    Args:
        result: 回測結果
        benchmark_comparison: compare_with_benchmark() 的結果（選用）
        output_path: 輸出路徑（None = 僅回傳 HTML 字串）

    Returns:
        HTML 字串
    """
    # 準備圖表資料
    nav = result.nav_series
    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in nav.index]
    nav_values = [round(float(v), 2) for v in nav.values]

    dd = result.drawdown_series
    dd_values = [round(float(v) * 100, 2) for v in dd.values]

    # 月報酬熱力圖數據
    monthly_returns = _compute_monthly_returns(result.daily_returns)

    # 基準比較數據
    bench_section = ""
    if benchmark_comparison and "error" not in benchmark_comparison:
        bc = benchmark_comparison
        bench_section = f"""
        <div class="section">
            <h2>基準比較 — {bc['benchmark_name']}</h2>
            <div class="grid">
                <div class="card">
                    <div class="card-label">超額報酬（年化）</div>
                    <div class="card-value {'positive' if bc['relative']['excess_return'] >= 0 else 'negative'}">
                        {bc['relative']['excess_return']:+.2%}
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">Information Ratio</div>
                    <div class="card-value">{bc['relative']['information_ratio']:.2f}</div>
                </div>
                <div class="card">
                    <div class="card-label">Beta</div>
                    <div class="card-value">{bc['relative']['beta']:.2f}</div>
                </div>
                <div class="card">
                    <div class="card-label">Alpha（年化）</div>
                    <div class="card-value {'positive' if bc['relative']['alpha'] >= 0 else 'negative'}">
                        {bc['relative']['alpha']:+.2%}
                    </div>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>指標</th><th>策略</th><th>{bc['benchmark_name']}</th></tr>
                </thead>
                <tbody>
                    <tr><td>總報酬</td><td>{bc['strategy']['total_return']:.2%}</td><td>{bc['benchmark']['total_return']:.2%}</td></tr>
                    <tr><td>年化報酬</td><td>{bc['strategy']['annual_return']:.2%}</td><td>{bc['benchmark']['annual_return']:.2%}</td></tr>
                    <tr><td>波動率</td><td>{bc['strategy']['volatility']:.2%}</td><td>{bc['benchmark']['volatility']:.2%}</td></tr>
                    <tr><td>Sharpe</td><td>{bc['strategy']['sharpe']:.2f}</td><td>{bc['benchmark']['sharpe']:.2f}</td></tr>
                    <tr><td>最大回撤</td><td>{bc['strategy']['max_drawdown']:.2%}</td><td>{bc['benchmark']['max_drawdown']:.2%}</td></tr>
                </tbody>
            </table>
        </div>
        """

    # 月報酬表格
    monthly_html = _monthly_returns_table(monthly_returns)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{result.strategy_name} — 回測報告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; padding: 24px; max-width: 1200px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
    h2 {{ font-size: 1.1rem; margin-bottom: 12px; color: #94a3b8; }}
    .header {{ margin-bottom: 24px; border-bottom: 1px solid #334155; padding-bottom: 16px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; }}
    .section {{ margin-bottom: 32px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 16px; }}
    .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 4px; }}
    .card-value {{ font-size: 1.25rem; font-weight: 600; }}
    .positive {{ color: #22c55e; }}
    .negative {{ color: #ef4444; }}
    .chart-container {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    canvas {{ max-height: 300px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 8px 12px; text-align: right; font-size: 0.85rem; }}
    th {{ background: #334155; color: #94a3b8; font-weight: 500; }}
    td {{ border-top: 1px solid #334155; }}
    td:first-child, th:first-child {{ text-align: left; }}
    .footer {{ color: #475569; font-size: 0.75rem; margin-top: 32px; text-align: center; }}
</style>
</head>
<body>

<div class="header">
    <h1>{result.strategy_name} 回測報告</h1>
    <div class="subtitle">
        {result.start_date} ~ {result.end_date} &nbsp;|&nbsp;
        初始資金 ${result.initial_cash:,.0f} &nbsp;|&nbsp;
        生成時間 {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
</div>

<div class="section">
    <h2>績效摘要</h2>
    <div class="grid">
        <div class="card">
            <div class="card-label">總報酬</div>
            <div class="card-value {'positive' if result.total_return >= 0 else 'negative'}">
                {result.total_return:+.2%}
            </div>
        </div>
        <div class="card">
            <div class="card-label">年化報酬</div>
            <div class="card-value {'positive' if result.annual_return >= 0 else 'negative'}">
                {result.annual_return:+.2%}
            </div>
        </div>
        <div class="card">
            <div class="card-label">Sharpe Ratio</div>
            <div class="card-value">{result.sharpe:.2f}</div>
        </div>
        <div class="card">
            <div class="card-label">Sortino Ratio</div>
            <div class="card-value">{result.sortino:.2f}</div>
        </div>
        <div class="card">
            <div class="card-label">Calmar Ratio</div>
            <div class="card-value">{result.calmar:.2f}</div>
        </div>
        <div class="card">
            <div class="card-label">最大回撤</div>
            <div class="card-value negative">{result.max_drawdown:.2%}</div>
        </div>
        <div class="card">
            <div class="card-label">波動率</div>
            <div class="card-value">{result.volatility:.2%}</div>
        </div>
        <div class="card">
            <div class="card-label">交易筆數</div>
            <div class="card-value">{result.total_trades}</div>
        </div>
        <div class="card">
            <div class="card-label">勝率</div>
            <div class="card-value">{result.win_rate:.1%}</div>
        </div>
        <div class="card">
            <div class="card-label">總手續費</div>
            <div class="card-value">${result.total_commission:,.0f}</div>
        </div>
    </div>
</div>

<div class="section">
    <h2>淨值曲線</h2>
    <div class="chart-container">
        <canvas id="navChart"></canvas>
    </div>
</div>

<div class="section">
    <h2>回撤</h2>
    <div class="chart-container">
        <canvas id="ddChart"></canvas>
    </div>
</div>

{bench_section}

<div class="section">
    <h2>月度報酬</h2>
    {monthly_html}
</div>

<div class="footer">
    Quant Trading System &mdash; 自動生成報告
</div>

<script>
const dates = {json.dumps(dates)};
const navData = {json.dumps(nav_values)};
const ddData = {json.dumps(dd_values)};

const chartDefaults = {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
        x: {{ ticks: {{ maxTicksLimit: 12, color: '#64748b' }}, grid: {{ color: '#334155' }} }},
        y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#334155' }} }}
    }}
}};

new Chart(document.getElementById('navChart'), {{
    type: 'line',
    data: {{
        labels: dates,
        datasets: [{{ data: navData, borderColor: '#3b82f6', borderWidth: 1.5, pointRadius: 0, fill: false }}]
    }},
    options: {{ ...chartDefaults, scales: {{
        ...chartDefaults.scales,
        y: {{ ...chartDefaults.scales.y, ticks: {{ ...chartDefaults.scales.y.ticks,
            callback: v => '$' + (v/1e6).toFixed(1) + 'M'
        }} }}
    }} }}
}});

new Chart(document.getElementById('ddChart'), {{
    type: 'line',
    data: {{
        labels: dates,
        datasets: [{{ data: ddData, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)',
                      borderWidth: 1.5, pointRadius: 0, fill: true }}]
    }},
    options: {{ ...chartDefaults, scales: {{
        ...chartDefaults.scales,
        y: {{ ...chartDefaults.scales.y, ticks: {{ ...chartDefaults.scales.y.ticks,
            callback: v => v.toFixed(1) + '%'
        }} }}
    }} }}
}});
</script>
</body>
</html>"""

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")
        logger.info("HTML report saved to %s", output_path)

    return html


def _compute_monthly_returns(daily_returns: pd.Series) -> pd.DataFrame:
    """計算月度報酬矩陣（rows=年, columns=月）。"""
    if daily_returns.empty:
        return pd.DataFrame()

    dr = daily_returns.copy()
    dr.index = pd.to_datetime(dr.index)

    monthly = (1 + dr).resample("ME").prod() - 1
    idx = pd.DatetimeIndex(monthly.index)
    monthly_df = pd.DataFrame({
        "year": idx.year,
        "month": idx.month,
        "return": monthly.values,
    })

    pivot = monthly_df.pivot(index="year", columns="month", values="return")
    def _compound(x: pd.Series[float]) -> float:
        from typing import cast as _cast
        return _cast(float, (1 + x).prod()) - 1

    yearly = monthly_df.groupby("year")["return"].apply(_compound)
    pivot["YTD"] = yearly
    return pivot


def _monthly_returns_table(monthly: pd.DataFrame) -> str:
    """將月度報酬矩陣轉為 HTML 表格。"""
    if monthly.empty:
        return "<p>No monthly return data</p>"

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "YTD"]
    cols = list(range(1, 13)) + ["YTD"]

    rows = []
    for year in sorted(monthly.index):
        cells = [f"<td><strong>{year}</strong></td>"]
        for c in cols:
            val = monthly.loc[year].get(c)
            if pd.isna(val) or val is None:
                cells.append("<td>—</td>")
            else:
                color = "positive" if val >= 0 else "negative"
                cells.append(f'<td class="{color}">{val:+.1%}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header = "<tr>" + "<th>Year</th>" + "".join(f"<th>{m}</th>" for m in month_names) + "</tr>"
    return f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
