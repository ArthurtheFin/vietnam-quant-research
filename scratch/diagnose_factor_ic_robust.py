"""One-off diagnostic (not part of the codebase): re-test the 44 technical
candidates from scratch/diagnose_broad_factor_ic.py fixing two methodology
issues before accepting the comprehensive-negative conclusion:

1. Newey-West HAC standard errors. The prior script sampled IC only every
   20 trading days specifically to avoid overlapping forward-return windows
   -- but that throws away ~95% of the daily cross-sections. This script
   instead computes IC on EVERY trading day (deliberately reintroducing
   overlap in the 20-day-forward target across consecutive days) and
   corrects the resulting autocorrelation with Newey-West (maxlags=20,
   matching the horizon) via statsmodels OLS HAC covariance, reporting the
   naive t-stat alongside for comparison.

2. Residualized target. Raw forward_return_20d is dominated by market beta
   and sector membership, which can swamp any idiosyncratic, stock-specific
   signal a factor might carry. Residualizes in two steps, both using only
   past information for the beta estimate (never the target itself):
     a) market-residual = fwd_ret_20d - beta_t * fwd_ret_20d_index, where
        beta_t is estimated from a trailing 250-session rolling regression
        of the stock's OWN daily returns on VNINDEX daily returns, ending at
        t (point-in-time, no look-ahead).
     b) sector-demean: subtract the cross-sectional mean of the market-
        residual across same-sector, same-day eligible names (config/sector_map.csv,
        96%+ coverage -- the "sector" column embedded in
        stealth_accumulation_history.parquet is 95% "Unclassified" and
        unusable for this).

3. Liquidity subset. Re-runs everything on both the full eligible universe
   and a top-150-by-trailing-60-session-median-traded-value subset,
   rebalanced monthly (~21 sessions), using only past data at each
   rebalance point (point-in-time, no survivorship bias).

4. Horizon diagnostic (light, informational only, more tests = higher false
   positive risk): for the 5 factors with the highest |t_NW| in the primary
   full-residualized-vs-top150 comparison, also computes 5d/10d/60d IC with
   matching Newey-West lag.

Constraints honored: no new factors, no factor-parameter tuning this pass;
conclusion threshold stays |t_NW| > 3 to account for the ~176 comparisons in
the main table.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

# statsmodels is broken in this environment (incompatible with the installed
# scipy 1.17 -- ImportError on statsmodels.distributions.discrete, an
# unrelated pre-existing environment issue, not touched here). Newey-West
# HAC standard error for a constant-only regression (i.e. testing whether
# mean(y) != 0) is implemented directly instead, per the fallback option:
# Var_HAC = (1/n) * [gamma_0 + 2 * sum_{k=1}^{maxlags} (1 - k/(maxlags+1)) * gamma_k]
# with gamma_k the sample autocovariance at lag k (Bartlett kernel) -- this
# is exactly what sm.OLS(y, const).fit(cov_type="HAC", cov_kwds={"maxlags":L})
# would produce for a constant-only design matrix.
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

t0 = time.time()

# ---------------------------------------------------------------------------
# 1. Load + zero-fill corporate-action handling (least destructive, matches
#    scratch/test_corp_action_zerofill_alternative.py)
# ---------------------------------------------------------------------------
df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

bench = read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
bench = bench.sort_values("date").reset_index(drop=True)


def zerofill_returns(frame: pd.DataFrame, group_col: str | None, horizon: int = 20) -> pd.DataFrame:
    out = frame.copy()
    ret1d = out["return_1d"].where(~out["suspect_corporate_action"], 0.0)
    grouped = ret1d.groupby(out[group_col]) if group_col else ret1d
    out["return_1d_zf"] = ret1d
    out[f"return_{horizon}d"] = grouped.transform(
        lambda s: (1.0 + s).rolling(horizon).apply(np.prod, raw=True) - 1.0
    ) if group_col else (1.0 + ret1d).rolling(horizon).apply(np.prod, raw=True) - 1.0
    out[f"forward_return_{horizon}d"] = grouped.transform(
        lambda s: (1.0 + s.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    ) if group_col else (1.0 + ret1d.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    return out


df = zerofill_returns(df, "symbol", horizon=20)
bench = zerofill_returns(bench, None, horizon=20)
bench_by_date = bench.set_index("date")[["return_1d_zf", "forward_return_20d"]].rename(
    columns={"return_1d_zf": "index_return_1d", "forward_return_20d": "index_forward_return_20d"}
)
print(f"[{time.time()-t0:.0f}s] loaded + zero-filled: {len(df)} rows, {df['symbol'].nunique()} symbols")

# ---------------------------------------------------------------------------
# 2. Rolling beta (250-session trailing, point-in-time) + market-residual target
# ---------------------------------------------------------------------------
df = df.merge(bench_by_date, left_on="date", right_index=True, how="left")

BETA_WINDOW = 250


def rolling_beta(group: pd.DataFrame) -> pd.Series:
    cov = group["return_1d_zf"].rolling(BETA_WINDOW, min_periods=100).cov(group["index_return_1d"])
    var = group["index_return_1d"].rolling(BETA_WINDOW, min_periods=100).var()
    return cov / var.replace(0, np.nan)


df["beta_250d"] = df.groupby("symbol", group_keys=False).apply(rolling_beta)
df["market_residual_20d"] = df["forward_return_20d"] - df["beta_250d"] * df["index_forward_return_20d"]
print(f"[{time.time()-t0:.0f}s] rolling beta + market-residual computed "
      f"(beta non-null: {df['beta_250d'].notna().sum()}/{len(df)})")

# ---------------------------------------------------------------------------
# 3. Sector-demean (config/sector_map.csv, ~96% coverage, static point-in-time map)
# ---------------------------------------------------------------------------
sector_map = pd.read_csv("config/sector_map.csv")[["symbol", "sector"]]
df = df.merge(sector_map, on="symbol", how="left", suffixes=("", "_map"))
df["sector"] = df["sector_map"].fillna("UNKNOWN")
df = df.drop(columns=["sector_map"])
print(f"[{time.time()-t0:.0f}s] sector map coverage: "
      f"{(df['sector'] != 'UNKNOWN').mean():.1%} of rows")


def sector_demean(frame: pd.DataFrame, value_col: str, eligible_mask: pd.Series) -> pd.Series:
    work = frame.loc[eligible_mask, ["date", "sector", value_col]].copy()
    sector_mean = work.groupby(["date", "sector"])[value_col].transform("mean")
    out = pd.Series(np.nan, index=frame.index)
    out.loc[eligible_mask] = work[value_col] - sector_mean
    return out


# ---------------------------------------------------------------------------
# 4. Universe construction: full eligible vs top-150-liquidity
# ---------------------------------------------------------------------------
REBALANCE_PERIOD = 21  # ~1 month
LIQUIDITY_LOOKBACK = 60
TOP_N = 150
MIN_VALUE_MA20 = 3_000_000_000.0  # lowered from 10B (see docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md
# Round 5 / docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md open question #1): 10B was too strict for
# 2020-2022 under the pre-backfill dataset; full_history_v2 now has clean
# 2020+ coverage, so the threshold is revisited to let that period contribute.

df["median_value_60d"] = df.groupby("symbol")["value"].transform(
    lambda s: s.rolling(LIQUIDITY_LOOKBACK, min_periods=30).median()
)

all_dates = sorted(df["date"].unique())
monthly_rebalance_dates = all_dates[::REBALANCE_PERIOD]

top150_membership: dict[pd.Timestamp, set[str]] = {}
for rd in monthly_rebalance_dates:
    snap = df[df["date"] == rd][["symbol", "median_value_60d"]].dropna()
    top150_membership[rd] = set(snap.sort_values("median_value_60d", ascending=False).head(TOP_N)["symbol"])

# forward-fill membership: each day uses the most recent (<= that day) monthly rebalance's set
rebalance_arr = np.array(monthly_rebalance_dates)


def membership_for_date(d: pd.Timestamp) -> set[str]:
    idx = np.searchsorted(rebalance_arr, d, side="right") - 1
    if idx < 0:
        return set()
    return top150_membership[rebalance_arr[idx]]


date_to_top150 = {d: membership_for_date(d) for d in all_dates}
df["in_top150"] = df.apply(lambda row: row["symbol"] in date_to_top150.get(row["date"], set()), axis=1)
print(f"[{time.time()-t0:.0f}s] top-150 membership computed "
      f"(avg symbols/day: {df.groupby('date')['in_top150'].sum().mean():.0f})")

# base eligibility (both universes): above_ma200 trend filter, matches prior scripts
df["eligible_full"] = df["above_ma200"].astype(bool) & (df["value_ma20"].fillna(0) >= MIN_VALUE_MA20)
df["eligible_top150"] = df["above_ma200"].astype(bool) & df["in_top150"]

# ---------------------------------------------------------------------------
# 5. Residualized target = market-residual, sector-demeaned, per universe
#    (sector-demean computed separately per universe since the eligible set differs)
# ---------------------------------------------------------------------------
df["target_resid_full"] = sector_demean(df, "market_residual_20d", df["eligible_full"] & df["market_residual_20d"].notna())
df["target_resid_top150"] = sector_demean(df, "market_residual_20d", df["eligible_top150"] & df["market_residual_20d"].notna())
print(f"[{time.time()-t0:.0f}s] sector-demeaned residual target ready")

CANDIDATES = [
    "distance_ma20", "return_20d", "realized_vol_20d",
    "return_5d", "return_10d", "return_60d", "distance_ma50", "distance_ma200",
    "relative_strength_20d", "sector_relative_strength_20d", "sector_tailwind_20d",
    "market_down_alpha_20d", "higher_low_ratio",
    "atr_pct_14", "volatility_percentile", "dist_skew_60d", "dist_kurt_60d", "tail_ratio_60d",
    "value_ma20", "volume_zscore_20d", "value_zscore_20d", "volume_ratio_5_20",
    "value_ratio_10_60", "up_down_value_ratio_10d", "up_down_volume_ratio",
    "bb_width", "bb_width_percentile", "price_position_20d", "pullback_from_high_20d",
    "distance_to_pivot", "close_location_value", "upper_wick_pct", "base_range_percentile",
    "accumulation_score", "breakout_quality_score", "relative_strength_score", "pressure_score",
    "near_pivot_score", "liquidity_score", "tight_range_score", "volatility_dryup_score",
    "quiet_volume_score", "absorption_score", "breadth_support_score", "sector_support_score",
    "market_support_score", "volatility_support_score", "net_accumulation_score",
]
MIN_ELIGIBLE = 15


def daily_ic_series(frame: pd.DataFrame, eligible_col: str, target_col: str, factor_col: str) -> pd.Series:
    sub = frame.loc[frame[eligible_col] & frame[target_col].notna() & frame[factor_col].notna(),
                     ["date", target_col, factor_col]]
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= MIN_ELIGIBLE].index
    sub = sub[sub["date"].isin(valid_dates)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"))


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


# ---------------------------------------------------------------------------
# Main table: factor x universe x target
# ---------------------------------------------------------------------------
UNIVERSES = {"full": ("eligible_full", "forward_return_20d", "target_resid_full")}
UNIVERSES["top150"] = ("eligible_top150", "forward_return_20d", "target_resid_top150")

rows = []
for uname, (elig_col, raw_target_col, resid_target_col) in UNIVERSES.items():
    for target_label, target_col in [("raw", raw_target_col), ("residualized", resid_target_col)]:
        for factor in CANDIDATES:
            ic_series = daily_ic_series(df, elig_col, target_col, factor)
            mean_ic, naive_t, nw_t, n = newey_west_tstat(ic_series, maxlags=20)
            rows.append({
                "factor": factor, "universe": uname, "target": target_label,
                "mean_IC": mean_ic, "t_naive": naive_t, "t_NW": nw_t, "n_days": n,
            })
    print(f"[{time.time()-t0:.0f}s] universe={uname} done")

result = pd.DataFrame(rows)
result["abs_t_NW"] = result["t_NW"].abs()
result = result.sort_values("abs_t_NW", ascending=False)
# GD5 NV2/NV4 (docs/reports/scoring/docs/reports/scoring/ROBUSTNESS_REPORT.md): save the raw table for FDR analysis and
# for re-checking realized_vol_20d/value_ma20's t_NW on current data -- output
# capture only, no change to the methodology above.
result.to_csv("data/output/factor_retest_v2_rerun_gd5.csv", index=False)

pd.set_option("display.width", 160)
pd.set_option("display.max_rows", 250)
print(f"\n[{time.time()-t0:.0f}s] === MAIN TABLE (factor x universe x target, sorted by |t_NW|) ===\n")
print(result[["factor", "universe", "target", "mean_IC", "t_naive", "t_NW", "n_days"]].to_string(index=False,
      formatters={"mean_IC": "{:+.4f}".format, "t_naive": "{:+.2f}".format, "t_NW": "{:+.2f}".format}))

n_over_3 = (result["abs_t_NW"] > 3).sum()
print(f"\nCombinations with |t_NW| > 3: {n_over_3} of {len(result)}")

# ---------------------------------------------------------------------------
# Task 4: horizon diagnostic for the top-5 |t_NW| factors (informational only)
# ---------------------------------------------------------------------------
top5 = result.head(5)
print(f"\n=== Task 4 (DIAGNOSTIC ONLY, more tests = higher false-positive risk): "
      f"horizon check for top-5 |t_NW| combos ===\n")
for _, row in top5.iterrows():
    factor, uname, target_label = row["factor"], row["universe"], row["target"]
    elig_col, raw_target_col, resid_target_col = UNIVERSES[uname]
    base_target_col = raw_target_col if target_label == "raw" else resid_target_col
    print(f"-- {factor} | {uname} | {target_label} (20d: t_NW={row['t_NW']:+.2f}) --")
    for horizon in (5, 10, 60):
        df_h = zerofill_returns(df[["symbol", "date", "return_1d", "suspect_corporate_action"]].copy(), "symbol", horizon=horizon)
        h_fwd_col = f"forward_return_{horizon}d"
        merged = df.copy()
        merged[h_fwd_col] = df_h[h_fwd_col].values
        if target_label == "raw":
            h_target_col = h_fwd_col
        else:
            bench_h = zerofill_returns(bench[["date", "return_1d", "suspect_corporate_action"]].copy(), None, horizon=horizon)
            merged = merged.merge(
                bench_h[["date", h_fwd_col]].rename(columns={h_fwd_col: f"index_{h_fwd_col}"}), on="date", how="left"
            )
            merged[f"market_residual_{horizon}d"] = merged[h_fwd_col] - merged["beta_250d"] * merged[f"index_{h_fwd_col}"]
            merged[f"target_resid_{horizon}d_{uname}"] = sector_demean(
                merged, f"market_residual_{horizon}d", merged[elig_col] & merged[f"market_residual_{horizon}d"].notna()
            )
            h_target_col = f"target_resid_{horizon}d_{uname}"
        ic_series_h = daily_ic_series(merged, elig_col, h_target_col, factor)
        mean_ic_h, naive_t_h, nw_t_h, n_h = newey_west_tstat(ic_series_h, maxlags=horizon)
        print(f"    horizon={horizon:3d}d  mean_IC={mean_ic_h:+.4f}  t_naive={naive_t_h:+.2f}  "
              f"t_NW={nw_t_h:+.2f}  N={n_h}")

print(f"\n[{time.time()-t0:.0f}s] done")
