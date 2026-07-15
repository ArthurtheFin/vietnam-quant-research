"""GD4 NV2 -- run WATCHLIST_VALIDATION_PREREG.md exactly as locked. One run,
no parameter tuning after seeing results. Reuses (does not redefine)
final_watchlist.py's own _score()/_mark_filters()/_merge_benchmark(), the
Newey-West/residualization/top-150 machinery from scratch/score_v2_ic_test.py,
and the null-test machinery from scratch/score_v2_null_test.py.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.screening.final_watchlist import (
    DEFAULT_FINAL_WATCHLIST_CONFIG,
    _mark_filters,
    _merge_benchmark,
    _score,
)
from src.validation.trading_status import latest_trading_status
from src.validation.guards import assert_no_forward_columns

t0 = time.time()
SEED = 42
N_ITER = 2000
MIN_ELIGIBLE = 15


def log(msg):
    print(f"[{time.time()-t0:.0f}s] {msg}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# 1. Load + universe (trading_status ACTIVE, current snapshot)
# ---------------------------------------------------------------------------
features = read_parquet("data/processed/stock_features.parquet")
features["date"] = pd.to_datetime(features["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])
meta_ranking = read_parquet("data/signals/meta_ranking.parquet")
meta_date_col = "analysis_date" if "analysis_date" in meta_ranking.columns else "date"
meta_ranking[meta_date_col] = pd.to_datetime(meta_ranking[meta_date_col])
sector_df = pd.read_csv("config/sector_map.csv")
sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))

active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])
log(f"ACTIVE symbols: {len(active_symbols)}")

# ---------------------------------------------------------------------------
# 2. Zero-fill forward_return_20d (same convention as scratch/score_v2_ic_test.py)
# ---------------------------------------------------------------------------
def zerofill_returns(frame: pd.DataFrame, group_col: str | None, horizon: int = 20) -> pd.DataFrame:
    out = frame.copy()
    ret1d = out["return_1d"].where(~out["suspect_corporate_action"], 0.0)
    grouped = ret1d.groupby(out[group_col]) if group_col else ret1d
    out["return_1d_zf"] = ret1d
    out[f"forward_return_{horizon}d"] = grouped.transform(
        lambda s: (1.0 + s.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    ) if group_col else (1.0 + ret1d.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    return out


features = features.sort_values(["symbol", "date"]).reset_index(drop=True)
features = zerofill_returns(features, "symbol", horizon=20)
bench_zf = zerofill_returns(benchmark.sort_values("date").reset_index(drop=True), None, horizon=20)
bench_by_date = bench_zf.set_index("date")[["return_1d_zf", "forward_return_20d"]].rename(
    columns={"return_1d_zf": "index_return_1d", "forward_return_20d": "index_forward_return_20d"}
)
features = features.merge(bench_by_date, left_on="date", right_index=True, how="left")

BETA_WINDOW = 250


def rolling_beta(group: pd.DataFrame) -> pd.Series:
    cov = group["return_1d_zf"].rolling(BETA_WINDOW, min_periods=100).cov(group["index_return_1d"])
    var = group["index_return_1d"].rolling(BETA_WINDOW, min_periods=100).var()
    return cov / var.replace(0, np.nan)


features["beta_250d"] = features.groupby("symbol", group_keys=False).apply(rolling_beta, include_groups=False)
features["market_residual_20d"] = features["forward_return_20d"] - features["beta_250d"] * features["index_forward_return_20d"]

features = features.merge(sector_df[["symbol", "sector"]], on="symbol", how="left")
features["sector"] = features["sector"].fillna("UNKNOWN")
log("zero-fill + rolling beta + sector map ready")


def sector_demean(frame: pd.DataFrame, value_col: str, eligible_mask: pd.Series) -> pd.Series:
    work = frame.loc[eligible_mask, ["date", "sector", value_col]].copy()
    sector_mean = work.groupby(["date", "sector"])[value_col].transform("mean")
    out = pd.Series(np.nan, index=frame.index)
    out.loc[eligible_mask] = work[value_col] - sector_mean
    return out


# ---------------------------------------------------------------------------
# 3. Universes: full (ACTIVE) + top150 (trailing 60d median value, monthly, ACTIVE)
# ---------------------------------------------------------------------------
features["is_active"] = features["symbol"].isin(active_symbols)
features["median_value_60d"] = features.groupby("symbol")["value"].transform(
    lambda s: s.rolling(60, min_periods=30).median()
)
REBALANCE_PERIOD = 21
TOP_N = 150
all_dates = sorted(features["date"].unique())
monthly_rebalance_dates = all_dates[::REBALANCE_PERIOD]
top150_membership: dict = {}
for rd in monthly_rebalance_dates:
    snap = features[(features["date"] == rd) & features["is_active"]][["symbol", "median_value_60d"]].dropna()
    top150_membership[rd] = set(snap.sort_values("median_value_60d", ascending=False).head(TOP_N)["symbol"])
rebalance_arr = np.array(monthly_rebalance_dates)


def membership_for_date(d):
    idx = np.searchsorted(rebalance_arr, d, side="right") - 1
    return top150_membership[rebalance_arr[idx]] if idx >= 0 else set()


date_to_top150 = {d: membership_for_date(d) for d in all_dates}
features["in_top150"] = features.apply(lambda row: row["symbol"] in date_to_top150.get(row["date"], set()), axis=1)
features["eligible_full"] = features["is_active"]
features["eligible_top150"] = features["is_active"] & features["in_top150"]

features["target_resid_full"] = sector_demean(features, "market_residual_20d", features["eligible_full"] & features["market_residual_20d"].notna())
features["target_resid_top150"] = sector_demean(features, "market_residual_20d", features["eligible_top150"] & features["market_residual_20d"].notna())
log(f"universes ready (full ACTIVE={features['is_active'].sum()>0}, avg top150/day={features.groupby('date')['in_top150'].sum().mean():.0f})")

# ---------------------------------------------------------------------------
# 4. Compute final_watchlist's own component scores + composite, per day,
#    reusing _score() unmodified. Also v2_score and strict_pass/fallback_eligible
#    (for the "watchlist toi gian" baseline) reusing _mark_filters() unmodified.
# ---------------------------------------------------------------------------
panel = features.copy()
panel["history_days"] = panel.groupby("symbol").cumcount() + 1
panel["ma50_slope_20d"] = panel.groupby("symbol")["ma50"].transform(lambda s: s / s.shift(20) - 1.0)
panel["above_ma20"] = panel["above_ma20"].fillna(False)
panel["above_ma50"] = panel["above_ma50"].fillna(False)
panel["above_ma200"] = panel["above_ma200"].fillna(False)
panel["market_regime"] = np.nan  # not point-in-time reconstructable historically; _warnings/_score don't require it for the score itself

# benchmark merge for excess_return_20d/60d (reuse _merge_benchmark unmodified)
panel = _merge_benchmark(panel, benchmark)

# as-of merge of meta_ranking (risk_penalty_score, meta_score, trade_edge_score, setup_quality_score)
meta_cols = ["symbol", meta_date_col, "meta_score", "trade_edge_score", "setup_quality_score", "risk_penalty_score"]
meta_small = meta_ranking[[c for c in meta_cols if c in meta_ranking.columns]].sort_values(meta_date_col)
panel = panel.sort_values("date")
panel = pd.merge_asof(
    panel, meta_small.rename(columns={meta_date_col: "date"}),
    on="date", by="symbol", direction="backward",
)
log(f"meta_ranking as-of merge done (meta_score non-null: {panel['meta_score'].notna().sum()}/{len(panel)})")

# drop forward columns before calling _score (assert_no_forward_columns raises otherwise)
score_input_cols = [c for c in panel.columns if "forward" not in c.lower() and "future" not in c.lower()]
panel_for_score = panel[score_input_cols].copy()

cfg = DEFAULT_FINAL_WATCHLIST_CONFIG


def score_day(g):
    return _score(g, cfg)


log("scoring cross-sectionally per day (this is the slow step)...")
scored_parts = []
mark_parts = []
for i, (d, g) in enumerate(panel_for_score.groupby("date")):
    s = _score(g, cfg)
    scored_parts.append(s[["symbol", "date", "trend_score", "momentum_score", "relative_strength_score",
                            "liquidity_score", "volume_score", "risk_score", "signal_score", "base_final_score"]])
    m = _mark_filters(g, cfg)
    mark_parts.append(m[["symbol", "date", "strict_pass", "fallback_eligible"]])
    if (i + 1) % 200 == 0:
        log(f"  scored {i+1}/{len(all_dates)} days")

scored = pd.concat(scored_parts, ignore_index=True)
marks = pd.concat(mark_parts, ignore_index=True)
panel = panel.merge(scored, on=["symbol", "date"], how="left")
panel = panel.merge(marks, on=["symbol", "date"], how="left")
log("component + composite scoring done")

# v2_score (cite v2's own numbers for its own IC/null test -- only need it here
# to build the "watchlist toi gian" ranking)
def score_day_v2(g):
    vol_score = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
    liq_score = (1.0 - g["value_ma20"].rank(pct=True, na_option="keep")) * 100.0
    g = g.copy()
    g["v2_score"] = 0.70 * vol_score.fillna(50.0) + 0.30 * liq_score.fillna(50.0)
    return g


panel = panel.groupby("date", group_keys=False).apply(score_day_v2, include_groups=True)
panel["minimal_eligible"] = panel["strict_pass"].fillna(False) | panel["fallback_eligible"].fillna(False)
log("v2_score + minimal-watchlist eligibility mask done")

panel.to_parquet("data/output/watchlist_validation_panel.parquet", index=False)
log(f"panel written: {len(panel)} rows")
