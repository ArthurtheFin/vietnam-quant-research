"""One-off diagnostic (not part of the codebase): reframe from IC (average
monotonic relationship) to EVENT DETECTION -- can any of the 44 technical
factors flag names about to have a tail-magnitude explosive move, ahead of
time? Pre-registered event definition and evaluation protocol (see chat);
event definition is fixed BEFORE looking at any factor results and is not
adjusted afterward.

Event(symbol, t) = 1 if:
  - excess_return_60d(t) = fwd_return_60d(symbol, t) - fwd_return_60d(index, t) >= +0.25
  - AND median_value_20d(symbol, t) (trailing, point-in-time) >= 1e9 VND/day
    (calibrated against the actual data distribution -- this threshold keeps
    56.7% of (symbol,date) rows, a reasonable liquid-but-not-too-narrow cut;
    not re-picked after seeing the event rate)

Task 1 prints the base rate (overall + by year) and HALTS before Task 2 if
it falls outside [1%, 15%] -- per instruction, not self-corrected.

Task 2: for each of the 44 factors, tested in BOTH ranking directions
("high" = top decile/quintile by highest raw value, "low" = top decile/
quintile by lowest raw value -- pre-registering both directions up front,
since the natural direction for TAIL-event capture need not match the
sign that was tested for average-return IC; this is not tuning after the
fact, both directions are scored under the identical bar). For each day,
computes pooled hit-count in the top bucket vs. pooled eligible/event
counts, so the lift statistic is a ratio of SUMS across days (robust to
small-sample noise on any single day), not a mean of noisy daily ratios.

Uncertainty: block bootstrap over TIME (block=60 trading days, 1000
resamples) resampling which DAYS enter the pooled tally, not a naive t-test
on a per-day ratio series (overlapping 60-day forward windows + cross-
sectional correlation make that invalid, per the same logic as the
Newey-West work).

Stability check: pooled lift computed separately within 3 equal calendar
periods; a factor-direction only "passes" if lift > 1 in all three AND the
bootstrap 95% CI lower bound for the (full-sample) lift exceeds 1.5.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

t0 = time.time()
rng = np.random.default_rng(20260709)

# ---------------------------------------------------------------------------
# Load + zero-fill corporate-action handling (consistent with prior work)
# ---------------------------------------------------------------------------
df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

bench = read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
bench = bench.sort_values("date").reset_index(drop=True)

HORIZON = 60


def zerofill_forward_return(frame: pd.DataFrame, group_col: str | None, horizon: int) -> pd.Series:
    ret1d = frame["return_1d"].where(~frame["suspect_corporate_action"], 0.0)
    grouped = ret1d.groupby(frame[group_col]) if group_col else ret1d
    if group_col:
        return grouped.transform(lambda s: (1.0 + s.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0)
    return (1.0 + ret1d.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0


df["forward_return_60d"] = zerofill_forward_return(df, "symbol", HORIZON)
bench["forward_return_60d"] = zerofill_forward_return(bench, None, HORIZON)
bench_by_date = bench.set_index("date")["forward_return_60d"].rename("index_forward_return_60d")
df = df.merge(bench_by_date, left_on="date", right_index=True, how="left")

df["excess_return_60d"] = df["forward_return_60d"] - df["index_forward_return_60d"]
df["median_value_20d"] = df.groupby("symbol")["value"].transform(lambda s: s.rolling(20, min_periods=10).median())

LIQUIDITY_THRESHOLD = 1_000_000_000.0  # 1B VND/day, ~56.7% of (symbol,date) rows pass -- see docstring
EVENT_RETURN_THRESHOLD = 0.25

defined = df["excess_return_60d"].notna() & df["median_value_20d"].notna()
df["event"] = np.where(
    defined,
    ((df["excess_return_60d"] >= EVENT_RETURN_THRESHOLD) & (df["median_value_20d"] >= LIQUIDITY_THRESHOLD)),
    np.nan,
)

print(f"[{time.time()-t0:.0f}s] loaded + event flag computed, {defined.sum()} defined (symbol,date) rows\n")

# ---------------------------------------------------------------------------
# TASK 1 -- base rate check (HALT if outside [1%, 15%])
# ---------------------------------------------------------------------------
base = df.loc[defined].copy()
overall_rate = base["event"].astype(bool).mean()
base["year"] = base["date"].dt.year
by_year = base.groupby("year")["event"].apply(lambda s: s.astype(bool).mean())

print("=== TASK 1: base rate check ===")
print(f"Overall base rate: {overall_rate:.2%}  (N={len(base)} defined symbol-days)")
print("By year:")
print(by_year.apply(lambda x: f"{x:.2%}").to_string())
print()

if not (0.01 <= overall_rate <= 0.15):
    print(f"!!! BASE RATE {overall_rate:.2%} IS OUTSIDE [1%, 15%] -- HALTING per instruction, not self-adjusting.")
    raise SystemExit(1)
print(f"Base rate {overall_rate:.2%} is within [1%, 15%] -- proceeding to Task 2.\n")

# ---------------------------------------------------------------------------
# TASK 2 -- factor evaluation under the event/lift framework
# ---------------------------------------------------------------------------
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

MIN_VALUE_MA20 = 10_000_000_000.0
MIN_ELIGIBLE = 15
REBALANCE_STEP = 1  # decision made every trading day (as in the robust IC re-test)

df["eligible"] = df["above_ma200"].astype(bool) & (df["value_ma20"].fillna(0) >= MIN_VALUE_MA20)

all_dates = sorted(df["date"].unique())
n_dates = len(all_dates)
period_bounds = [all_dates[0], all_dates[n_dates // 3], all_dates[2 * n_dates // 3], all_dates[-1]]
periods = [(period_bounds[i], period_bounds[i + 1]) for i in range(3)]
print(f"3 equal periods (by trading-day count): "
      f"{[(p[0].date().isoformat(), p[1].date().isoformat()) for p in periods]}\n")

# Precompute per-day eligible frames once (used by every factor)
daily_frames: dict[pd.Timestamp, pd.DataFrame] = {}
for d in all_dates:
    snap = df[(df["date"] == d) & df["eligible"] & df["event"].notna()]
    if len(snap) >= MIN_ELIGIBLE:
        daily_frames[d] = snap

usable_dates = sorted(daily_frames.keys())
print(f"[{time.time()-t0:.0f}s] {len(usable_dates)} usable days (eligible universe defined + event definable)\n")


def per_day_stats(factor: str, direction: str) -> np.ndarray:
    """One pass per (factor, direction): for every usable day, compute
    [h10, m10, h5, m5, e, n] in a single rank() call, reused for the full
    pooled lift, the 3-period breakdown, and the bootstrap -- avoids
    recomputing the same rank() repeatedly across those three consumers."""
    stats = np.zeros((len(usable_dates), 6), dtype=np.int64)
    for i, d in enumerate(usable_dates):
        snap = daily_frames[d]
        valid = snap[[factor, "event"]].dropna(subset=[factor])
        n = len(valid)
        if n < MIN_ELIGIBLE:
            continue
        pct_rank = valid[factor].rank(pct=True)
        events = valid["event"].astype(bool).values
        e = int(events.sum())
        in10 = (pct_rank >= 0.90).values if direction == "high" else (pct_rank <= 0.10).values
        in5 = (pct_rank >= 0.95).values if direction == "high" else (pct_rank <= 0.05).values
        h10, m10 = int(events[in10].sum()), int(in10.sum())
        h5, m5 = int(events[in5].sum()), int(in5.sum())
        stats[i] = [h10, m10, h5, m5, e, n]
    return stats


def lift_from_sums(sums: np.ndarray, h_idx: int, m_idx: int) -> float:
    h_sum, m_sum, e_sum, n_sum = sums[h_idx], sums[m_idx], sums[4], sums[5]
    if m_sum == 0 or n_sum == 0 or e_sum == 0:
        return np.nan
    precision = h_sum / m_sum
    base_rate = e_sum / n_sum
    return precision / base_rate if base_rate > 0 else np.nan


BLOCK_SIZE = 60
N_BOOTSTRAP = 1000

usable_dates_arr = np.array(usable_dates)
period_masks = [(usable_dates_arr >= p[0]) & (usable_dates_arr <= p[1]) for p in periods]


def block_bootstrap_ci(per_day: np.ndarray) -> tuple[float, float]:
    n = len(per_day)
    if n < BLOCK_SIZE * 3:
        return np.nan, np.nan
    n_blocks_needed = int(np.ceil(n / BLOCK_SIZE))
    max_start = n - BLOCK_SIZE
    boot_lifts = np.empty(N_BOOTSTRAP)
    for b in range(N_BOOTSTRAP):
        starts = rng.integers(0, max_start + 1, size=n_blocks_needed)
        idx = np.concatenate([np.arange(s, s + BLOCK_SIZE) for s in starts])[:n]
        sums = per_day[idx].sum(axis=0)
        boot_lifts[b] = lift_from_sums(sums, 0, 1)
    valid = boot_lifts[~np.isnan(boot_lifts)]
    if len(valid) < N_BOOTSTRAP * 0.5:
        return np.nan, np.nan
    return float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5))


rows = []
directions = ["high", "low"]
for factor in CANDIDATES:
    for direction in directions:
        per_day = per_day_stats(factor, direction)
        full_sums = per_day.sum(axis=0)
        lift10 = lift_from_sums(full_sums, 0, 1)
        lift5 = lift_from_sums(full_sums, 2, 3)
        period_lifts = [lift_from_sums(per_day[mask].sum(axis=0), 0, 1) for mask in period_masks]
        ci_lo, ci_hi = block_bootstrap_ci(per_day)
        rows.append({
            "factor": factor, "direction": direction,
            "lift_10pct": lift10, "lift_5pct": lift5,
            "ci_lo_95": ci_lo, "ci_hi_95": ci_hi,
            "lift_p1": period_lifts[0], "lift_p2": period_lifts[1], "lift_p3": period_lifts[2],
        })
    print(f"[{time.time()-t0:.0f}s] {factor} done")

result = pd.DataFrame(rows)
result["passes"] = (
    (result["ci_lo_95"] > 1.5)
    & (result["lift_p1"] > 1) & (result["lift_p2"] > 1) & (result["lift_p3"] > 1)
)
result = result.sort_values("lift_10pct", ascending=False)

pd.set_option("display.width", 180)
pd.set_option("display.max_rows", 120)
print(f"\n[{time.time()-t0:.0f}s] === MAIN TABLE (factor x direction, sorted by lift@10%) ===\n")
print(result.to_string(index=False, formatters={
    c: "{:+.2f}".format for c in ["lift_10pct", "lift_5pct", "ci_lo_95", "ci_hi_95", "lift_p1", "lift_p2", "lift_p3"]
}))

passing = result[result["passes"]]
print(f"\nFactor-directions passing (CI_lo>1.5 AND lift>1 in all 3 periods): {len(passing)}")
if not passing.empty:
    print(passing[["factor", "direction", "lift_10pct", "ci_lo_95"]].to_string(index=False))

# ---------------------------------------------------------------------------
# TASK 3 -- sanity check for the single best factor-direction: liquidity distribution of captured hits
# ---------------------------------------------------------------------------
best = result.iloc[0]
factor_b, direction_b = best["factor"], best["direction"]
print(f"\n=== Sanity check: liquidity distribution of top-decile HITS for best factor ({factor_b}, {direction_b}) ===")
hit_liquidity = []
for d in usable_dates:
    snap = daily_frames[d]
    valid = snap[["date", factor_b, "event", "median_value_20d"]].dropna(subset=[factor_b])
    if len(valid) < MIN_ELIGIBLE:
        continue
    pct_rank = valid[factor_b].rank(pct=True)
    in_bucket = (pct_rank >= 0.90) if direction_b == "high" else (pct_rank <= 0.10)
    hits = valid[in_bucket & valid["event"].astype(bool)]
    hit_liquidity.extend(hits["median_value_20d"].tolist())

if hit_liquidity:
    hit_arr = np.array(hit_liquidity)
    near_threshold = (hit_arr < LIQUIDITY_THRESHOLD * 3).mean()
    print(f"N hits (top decile, event=True) = {len(hit_arr)}")
    print(pd.Series(hit_arr).describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]))
    print(f"Fraction of hits with median_value_20d < 3x threshold ({LIQUIDITY_THRESHOLD*3/1e9:.1f}B VND): {near_threshold:.1%}")
else:
    print("No hits found in top decile for the best factor-direction.")

print(f"\n[{time.time()-t0:.0f}s] done")
