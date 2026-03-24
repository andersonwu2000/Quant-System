"""
因子正交化 — 去除因子間共線性，確保多因子合成時每個因子帶來獨立信息。

兩種方法：
- 逐步正交化 (Gram-Schmidt)：有明確因子優先級時使用
- 對稱正交化 (PCA)：所有因子地位平等時使用
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def orthogonalize_sequential(
    factor_dict: dict[str, pd.DataFrame],
    priority: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    逐步正交化（改良 Gram-Schmidt）。

    按 priority 順序，每個因子回歸去除前面所有因子的影響，保留殘差。
    priority[0] 保持原樣，priority[1] 去除 [0] 的影響，以此類推。

    Args:
        factor_dict: {factor_name: DataFrame(index=date, columns=symbols)}
        priority: 因子優先級順序 (None = 按 dict 順序)
    """
    if not factor_dict:
        return {}

    names = priority if priority is not None else list(factor_dict.keys())
    # 驗證
    for n in names:
        if n not in factor_dict:
            raise ValueError(f"Factor '{n}' not in factor_dict")

    result: dict[str, pd.DataFrame] = {}

    for i, name in enumerate(names):
        if i == 0:
            result[name] = factor_dict[name].copy()
            continue

        current = factor_dict[name].copy()
        predecessors = [result[names[j]] for j in range(i)]

        # 逐日期橫截面回歸去除前置因子的影響
        for dt in current.index:
            y = current.loc[dt].dropna()
            if len(y) < 5:
                continue

            # 收集前置因子在此日期的值
            x_cols: list[pd.Series] = []
            for pred in predecessors:
                if dt in pred.index:
                    x_cols.append(pred.loc[dt])

            if not x_cols:
                continue

            # 對齊到共同 symbols
            x_df = pd.DataFrame(x_cols).T.dropna()
            common = y.index.intersection(x_df.index)
            if len(common) < max(len(x_cols) + 2, 5):
                continue

            y_arr = y[common].values.astype(float)
            x_arr = x_df.loc[common].values.astype(float)
            x_design = np.column_stack([np.ones(len(common)), x_arr])

            try:
                beta, _, _, _ = np.linalg.lstsq(x_design, y_arr, rcond=None)
                residuals = y_arr - x_design @ beta
                for j, sym in enumerate(common):
                    current.loc[dt, sym] = residuals[j]
            except np.linalg.LinAlgError:
                continue

        result[name] = current

    return result


def orthogonalize_symmetric(
    factor_dict: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """
    對稱正交化。

    對每個日期，將因子矩陣做 PCA 白化後旋轉回原空間，
    使因子兩兩正交但保持與原始因子最大對應。

    使用 ZCA (Zero-phase Component Analysis) 白化：W = V @ diag(1/sqrt(λ)) @ V^T
    """
    if not factor_dict:
        return {}

    names = list(factor_dict.keys())
    result_dfs = {name: factor_dict[name].copy() for name in names}

    # 取共同日期
    common_dates: set | None = None
    for df in factor_dict.values():
        if common_dates is None:
            common_dates = set(df.index)
        else:
            common_dates &= set(df.index)

    if not common_dates:
        return result_dfs

    for dt in sorted(common_dates):
        # 收集各因子在此日期的值
        series_list = []
        for name in names:
            s = factor_dict[name].loc[dt].dropna()
            series_list.append(s)

        # 對齊到共同 symbols
        common_symbols = series_list[0].index
        for s in series_list[1:]:
            common_symbols = common_symbols.intersection(s.index)

        if len(common_symbols) < len(names) + 2:
            continue

        # 構建因子矩陣 (n_stocks × n_factors)
        factor_matrix = np.column_stack([s[common_symbols].values for s in series_list]).astype(float)

        # 去均值
        mean = factor_matrix.mean(axis=0)
        centered = factor_matrix - mean

        # 協方差矩陣
        cov = np.cov(centered, rowvar=False)

        try:
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
        except np.linalg.LinAlgError:
            continue

        # 避免除以零
        eigenvalues = np.maximum(eigenvalues, 1e-10)

        # ZCA 白化矩陣
        zca_matrix = eigenvectors @ np.diag(1.0 / np.sqrt(eigenvalues)) @ eigenvectors.T
        whitened = centered @ zca_matrix

        # 寫回結果
        for j, name in enumerate(names):
            for k, sym in enumerate(common_symbols):
                result_dfs[name].loc[dt, sym] = whitened[k, j]

    return result_dfs


def factor_correlation_matrix(
    factor_dict: dict[str, pd.DataFrame],
    method: str = "spearman",
) -> pd.DataFrame:
    """
    計算因子間的平均橫截面相關矩陣。

    Args:
        factor_dict: {factor_name: DataFrame}
        method: "spearman" 或 "pearson"
    """
    names = list(factor_dict.keys())
    n = len(names)

    if n < 2:
        return pd.DataFrame(1.0, index=names, columns=names)

    # 取共同日期
    common_dates: set | None = None
    for df in factor_dict.values():
        if common_dates is None:
            common_dates = set(df.index)
        else:
            common_dates &= set(df.index)

    if not common_dates:
        return pd.DataFrame(np.nan, index=names, columns=names)

    corr_sum = np.zeros((n, n))
    count = 0

    for dt in sorted(common_dates):
        series = {}
        for name in names:
            s = factor_dict[name].loc[dt].dropna()
            series[name] = s

        # 對齊
        common_symbols = series[names[0]].index
        for name in names[1:]:
            common_symbols = common_symbols.intersection(series[name].index)

        if len(common_symbols) < 5:
            continue

        aligned = pd.DataFrame({name: series[name][common_symbols] for name in names})
        if method == "spearman":
            corr = aligned.rank().corr()
        else:
            corr = aligned.corr()

        if not corr.isna().any().any():
            corr_sum += corr.values
            count += 1

    if count == 0:
        return pd.DataFrame(np.nan, index=names, columns=names)

    avg_corr = corr_sum / count
    return pd.DataFrame(avg_corr, index=names, columns=names)
