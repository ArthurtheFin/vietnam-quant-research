"""docs/reports/scoring/SCORE_V2_DESIGN.md confirmation run, IC leg: v2_score run through the
exact canonical IC pipeline (scratch/diagnose_factor_ic_robust.py's
methodology), alongside alpha_score (old composite) and realized_vol_20d
(minimal score) for direct comparison. Newey-West maxlags=20, full+top150
universe, raw+residualized target, 3-period split.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.alpha.scoring import calculate_alpha_scores

df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

bench = read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
bench = bench.sort_values("date").reset_index(drop=True)


def _newey_west_mean_se(y: np.ndarray, maxlags: int) -> float:
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


def zerofill_returns(frame: pd.DataFrame, group_col: str | None, horizon: int = 20) -> pd.DataFrame:
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


def rolling_beta(group: pd.DataFrame) -> pd.Series:
    cov = group["return_1d_zf"].rolling(BETA_WINDOW, min_periods=100).cov(group["index_return_1d"])
    var = group["index_return_1d"].rolling(BETA_WINDOW, min_periods=100).var()
    return cov / var.replace(0, np.nan)


df["beta_250d"] = df.groupby("symbol", group_keys=False).apply(rolling_beta, include_groups=False)
df["market_residual_20d"] = df["forward_return_20d"] - df["beta_250d"] * df["index_forward_return_20d"]

sector_map_df = pd.read_csv("config/sector_map.csv")[["symbol", "sector"]]
df = df.merge(sector_map_df, on="symbol", how="left", suffixes=("", "_map"))
df["sector"] = df["sector_map"].fillna("UNKNOWN")
df = df.drop(columns=["sector_map"])


def sector_demean(frame: pd.DataFrame, value_col: str, eligible_mask: pd.Series) -> pd.Series:
    work = frame.loc[eligible_mask, ["date", "sector", value_col]].copy()
    sector_mean = work.groupby(["date", "sector"])[value_col].transform("mean")
    out = pd.Series(np.nan, index=frame.index)
    out.loc[eligible_mask] = work[value_col] - sector_mean
    return out


REBALANCE_PERIOD = 21
LIQUIDITY_LOOKBACK = 60
TOP_N = 150
MIN_VALUE_MA20 = 3_000_000_000.0

df["median_value_60d"] = df.groupby("symbol")["value"].transform(
    lambda s: s.rolling(LIQUIDITY_LOOKBACK, min_periods=30).median()
)
all_dates = sorted(df["date"].unique())
monthly_rebalance_dates = all_dates[::REBALANCE_PERIOD]
top150_membership: dict[pd.Timestamp, set[str]] = {}
for rd in monthly_rebalance_dates:
    snap = df[df["date"] == rd][["symbol", "median_value_60d"]].dropna()
    top150_membership[rd] = set(snap.sort_values("median_value_60d", ascending=False).head(TOP_N)["symbol"])
rebalance_arr = np.array(monthly_rebalance_dates)


def membership_for_date(d: pd.Timestamp) -> set[str]:
    idx = np.searchsorted(rebalance_arr, d, side="right") - 1
    if idx < 0:
        return set()
    return top150_membership[rebalance_arr[idx]]


date_to_top150 = {d: membership_for_date(d) for d in all_dates}
df["in_top150"] = df.apply(lambda row: row["symbol"] in date_to_top150.get(row["date"], set()), axis=1)

df["eligible_full"] = df["above_ma200"].astype(bool) & (df["value_ma20"].fillna(0) >= MIN_VALUE_MA20)
df["eligible_top150"] = df["above_ma200"].astype(bool) & df["in_top150"]

df["target_resid_full"] = sector_demean(df, "market_residual_20d", df["eligible_full"] & df["market_residual_20d"].notna())
df["target_resid_top150"] = sector_demean(df, "market_residual_20d", df["eligible_top150"] & df["market_residual_20d"].notna())

print("Computing deployed alpha_score (old composite) + v2_score for the full history...")
scored_old = calculate_alpha_scores(df, bench)
df["alpha_score"] = scored_old["alpha_score"].values


def _score_day_v2(g):
    vol_score = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
    liq_score = (1.0 - g["value_ma20"].rank(pct=True, na_option="keep")) * 100.0
    g["v2_score"] = 0.70 * vol_score.fillna(50.0) + 0.30 * liq_score.fillna(50.0)
    return g


df = df.groupby("date", group_keys=False).apply(_score_day_v2, include_groups=True)

CANDIDATES = ["v2_score", "alpha_score", "realized_vol_20d"]
MIN_ELIGIBLE = 15


def daily_ic_series(frame: pd.DataFrame, eligible_col: str, target_col: str, factor_col: str) -> pd.Series:
    sub = frame.loc[frame[eligible_col] & frame[target_col].notna() & frame[factor_col].notna(),
                     ["date", target_col, factor_col]]
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= MIN_ELIGIBLE].index
    sub = sub[sub["date"].isin(valid_dates)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"), include_groups=False)


def newey_west_tstat(ic_series: pd.Series, maxlags: int = 20) -> tuple[float, float, float, int]:
    ic_series = ic_series.dropna()
    n = len(ic_series)
    if n < 30:
        return np.nan, np.nan, np.nan, n
    y = ic_series.values
    mean_ic = y.mean()
    naive_t = mean_ic / y.std(ddof=1) * np.sqrt(n) if y.std(ddof=1) > 0 else np.nan
    nw_se = _newey_west_mean_se(y, maxlags=maxlags)
    nw_t = mean_ic / nw_se if nw_se > 0 else np.nan
    return mean_ic, naive_t, nw_t, n


UNIVERSES = {"full": ("eligible_full", "forward_return_20d", "target_resid_full"),
             "top150": ("eligible_top150", "forward_return_20d", "target_resid_top150")}

rows = []
for uname, (elig_col, raw_target_col, resid_target_col) in UNIVERSES.items():
    for target_label, target_col in [("raw", raw_target_col), ("residualized", resid_target_col)]:
        for factor in CANDIDATES:
            ic_series = daily_ic_series(df, elig_col, target_col, factor)
            mean_ic, naive_t, nw_t, n = newey_west_tstat(ic_series, maxlags=20)
            rows.append({"factor": factor, "universe": uname, "target": target_label,
                         "mean_IC": mean_ic, "t_naive": naive_t, "t_NW": nw_t, "n_days": n})

result = pd.DataFrame(rows)
pd.set_option("display.width", 160)
print("\n" + "=" * 90)
print("MAIN TABLE -- v2_score vs old composite (alpha_score) vs minimal (realized_vol_20d)")
print("Eligibility threshold: value_ma20 >= 3B VND (locked per docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md)")
print("=" * 90)
print(result.to_string(index=False, formatters={"mean_IC": "{:+.4f}".format, "t_naive": "{:+.2f}".format, "t_NW": "{:+.2f}".format}))

print("\n" + "=" * 90)
print("3-period split, full universe, residualized target")
print("=" * 90)
for factor in CANDIDATES:
    elig_col, raw_target_col, resid_target_col = UNIVERSES["full"]
    ic_series = daily_ic_series(df, elig_col, resid_target_col, factor).sort_index()
    n = len(ic_series)
    bounds = [ic_series.index[0], ic_series.index[n // 3], ic_series.index[2 * n // 3], ic_series.index[-1]]
    periods = [(bounds[i], bounds[i + 1]) for i in range(3)]
    print(f"\n{factor}:")
    signs = []
    for i, (p0, p1) in enumerate(periods, start=1):
        seg = ic_series[(ic_series.index >= p0) & (ic_series.index <= p1)]
        mean_ic, _, nw_t, n_seg = newey_west_tstat(seg, maxlags=20)
        signs.append(np.sign(mean_ic) if pd.notna(mean_ic) else 0)
        print(f"  Period {i} [{p0.date()}..{p1.date()}]: mean_IC={mean_ic:+.4f}  t_NW={nw_t:+.2f}  N={n_seg}")
    print(f"  Same-sign across all 3 periods: {len(set(signs)) == 1}")

print("\ndone")
