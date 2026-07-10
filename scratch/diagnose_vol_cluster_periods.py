"""NV1 follow-up: 3-period stability check for the volatility-cluster
representative candidates (atr_pct_14 vs. the currently-deployed
realized_vol_20d), full-universe residualized target -- same construction
as scratch/diagnose_factor_ic_robust.py, not re-derived.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

bench = read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
bench = bench.sort_values("date").reset_index(drop=True)


def zerofill_returns(frame, group_col, horizon=20):
    out = frame.copy()
    ret1d = out["return_1d"].where(~out["suspect_corporate_action"], 0.0)
    grouped = ret1d.groupby(out[group_col]) if group_col else ret1d
    out["return_1d_zf"] = ret1d
    out[f"forward_return_{horizon}d"] = grouped.transform(
        lambda s: (1.0 + s.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    ) if group_col else (1.0 + ret1d.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    return out


df = zerofill_returns(df, "symbol", horizon=20)
bench = zerofill_returns(bench, None, horizon=20)
bench_by_date = bench.set_index("date")[["return_1d_zf", "forward_return_20d"]].rename(
    columns={"return_1d_zf": "index_return_1d", "forward_return_20d": "index_forward_return_20d"}
)
df = df.merge(bench_by_date, left_on="date", right_index=True, how="left")

BETA_WINDOW = 250


def rolling_beta(group):
    cov = group["return_1d_zf"].rolling(BETA_WINDOW, min_periods=100).cov(group["index_return_1d"])
    var = group["index_return_1d"].rolling(BETA_WINDOW, min_periods=100).var()
    return cov / var.replace(0, np.nan)


df["beta_250d"] = df.groupby("symbol", group_keys=False).apply(rolling_beta)
df["market_residual_20d"] = df["forward_return_20d"] - df["beta_250d"] * df["index_forward_return_20d"]

sector_map = pd.read_csv("config/sector_map.csv")[["symbol", "sector"]]
df = df.merge(sector_map, on="symbol", how="left", suffixes=("", "_map"))
df["sector"] = df["sector_map"].fillna("UNKNOWN")
df = df.drop(columns=["sector_map"])

MIN_VALUE_MA20 = 3_000_000_000.0
df["eligible_full"] = df["above_ma200"].astype(bool) & (df["value_ma20"].fillna(0) >= MIN_VALUE_MA20)


def sector_demean(frame, value_col, eligible_mask):
    work = frame.loc[eligible_mask, ["date", "sector", value_col]].copy()
    sector_mean = work.groupby(["date", "sector"])[value_col].transform("mean")
    out = pd.Series(np.nan, index=frame.index)
    out.loc[eligible_mask] = work[value_col] - sector_mean
    return out


df["target_resid_full"] = sector_demean(df, "market_residual_20d", df["eligible_full"] & df["market_residual_20d"].notna())

MIN_ELIGIBLE = 15


def _newey_west_mean_se(y, maxlags):
    n = len(y)
    ybar = y.mean()
    demeaned = y - ybar
    gamma_0 = np.dot(demeaned, demeaned) / n
    variance = gamma_0
    for k in range(1, maxlags + 1):
        if k >= n:
            break
        gamma_k = np.dot(demeaned[k:], demeaned[:-k]) / n
        weight = 1.0 - k / (maxlags + 1)
        variance += 2.0 * weight * gamma_k
    return np.sqrt(variance / n)


def daily_ic_series(frame, eligible_col, target_col, factor_col):
    sub = frame.loc[frame[eligible_col] & frame[target_col].notna() & frame[factor_col].notna(),
                     ["date", target_col, factor_col]]
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= MIN_ELIGIBLE].index
    sub = sub[sub["date"].isin(valid_dates)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"), include_groups=False)


def newey_west_tstat(ic_series, maxlags=20):
    ic_series = ic_series.dropna()
    n = len(ic_series)
    if n < 30:
        return np.nan, np.nan, n
    y = ic_series.values
    mean_ic = y.mean()
    nw_se = _newey_west_mean_se(y, maxlags=maxlags)
    nw_t = mean_ic / nw_se if nw_se > 0 else np.nan
    return mean_ic, nw_t, n


for factor in ["realized_vol_20d", "atr_pct_14"]:
    ic_series = daily_ic_series(df, "eligible_full", "target_resid_full", factor)
    ic_series = ic_series.sort_index()
    n = len(ic_series)
    bounds = [ic_series.index[0], ic_series.index[n // 3], ic_series.index[2 * n // 3], ic_series.index[-1]]
    periods = [(bounds[i], bounds[i + 1]) for i in range(3)]
    print(f"=== {factor} (full universe, residualized target) ===")
    full_mean, full_t, full_n = newey_west_tstat(ic_series, maxlags=20)
    print(f"  FULL SAMPLE: mean_IC={full_mean:+.4f}  t_NW={full_t:+.2f}  N={full_n}")
    signs = []
    for i, (p0, p1) in enumerate(periods, start=1):
        seg = ic_series[(ic_series.index >= p0) & (ic_series.index <= p1)]
        mean_ic, nw_t, n_seg = newey_west_tstat(seg, maxlags=20)
        signs.append(np.sign(mean_ic) if pd.notna(mean_ic) else 0)
        print(f"  Period {i} [{p0.date()}..{p1.date()}]: mean_IC={mean_ic:+.4f}  t_NW={nw_t:+.2f}  N={n_seg}")
    same_sign = len(set(signs)) == 1
    print(f"  Same-sign IC across all 3 periods: {same_sign}\n")
