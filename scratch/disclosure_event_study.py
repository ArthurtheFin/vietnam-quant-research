"""NV2 -- run the disclosure event study exactly as locked in
docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md. One run, no parameter tuning after
seeing results. Writes data/disclosure/event_study_results.json for
docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md to cite.

Do not edit thresholds/windows/criteria here without also updating the
prereg first -- this script is meant to be a literal implementation of
the locked design, not a place to make new design choices.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.disclosure_parser import next_trading_day, load_market_holidays
from src.validation.trading_status import excluded_symbols_by_status


def _sha256_and_rows(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"sha256": None, "row_count": None}
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    rows = int(len(pd.read_parquet(p))) if p.suffix == ".parquet" else None
    return {"sha256": sha, "row_count": rows}


def build_lineage() -> dict:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=".")
    return {
        "git_commit_hash": commit.stdout.strip() if commit.returncode == 0 else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prereg_sha256": _sha256_and_rows("docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md")["sha256"],
        "inputs": {
            "data/disclosure/events.parquet": _sha256_and_rows("data/disclosure/events.parquet"),
            "data/processed/stock_features.parquet": _sha256_and_rows("data/processed/stock_features.parquet"),
            "data/processed/benchmark_vnindex.parquet": _sha256_and_rows("data/processed/benchmark_vnindex.parquet"),
            "data/full_history_v2/trading_status.parquet": _sha256_and_rows("data/full_history_v2/trading_status.parquet"),
            "data/raw/index_ohlcv/VNINDEX.parquet": _sha256_and_rows("data/raw/index_ohlcv/VNINDEX.parquet"),
        },
    }

LIQUIDITY_THRESHOLD = 3_000_000_000.0
SIGNAL_WINDOW_DAYS = 20
EXPLOSIVE_THRESHOLD = 0.25
N_BOOTSTRAP = 1000
BLOCK_SIZE = 60
RANDOM_STATE = 42
CAR_CLUSTER_GAP_DAYS = 20
CAR_HORIZONS = [20, 60, 120]
PERIODS = [
    ("period_1", pd.Timestamp("2020-01-01"), pd.Timestamp("2022-03-01")),
    ("period_2", pd.Timestamp("2022-03-01"), pd.Timestamp("2024-05-01")),
    ("period_3", pd.Timestamp("2024-05-01"), pd.Timestamp("2026-12-31")),
]
MIN_EVENTS_FOR_CONCLUSION = 30

SIGNAL_DEFS = {
    "S1_insider_related_buy": ("insider_registration", "buy"),
    "S2_major_shareholder_buy": ("major_shareholder_change", "buy"),
    "S3_insider_related_sell": ("insider_registration", "sell"),
}


def load_price_panel() -> pd.DataFrame:
    sf = pd.read_parquet(
        "data/processed/stock_features.parquet",
        columns=["symbol", "date", "value_ma20", "forward_return_60d"],
    )
    bench = pd.read_parquet(
        "data/processed/benchmark_vnindex.parquet", columns=["date", "forward_return_60d"]
    ).rename(columns={"forward_return_60d": "bench_fwd_60d"})
    panel = sf.merge(bench, on="date", how="left")
    panel["excess_fwd_60d"] = panel["forward_return_60d"] - panel["bench_fwd_60d"]
    panel["event"] = np.where(
        panel["excess_fwd_60d"].isna(), np.nan, (panel["excess_fwd_60d"] >= EXPLOSIVE_THRESHOLD).astype(float)
    )
    return panel


def build_eligible_panel(panel: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    excl = excluded_symbols_by_status()
    elig = panel[(panel["value_ma20"] >= LIQUIDITY_THRESHOLD) & (~panel["symbol"].isin(excl))].copy()
    day_idx_map = {d: i for i, d in enumerate(trading_days)}
    elig["day_idx"] = elig["date"].map(day_idx_map)
    elig = elig.dropna(subset=["day_idx"]).copy()
    elig["day_idx"] = elig["day_idx"].astype(int)
    # daily median liquidity split within the eligible pool itself
    elig["liq_group"] = elig.groupby("date")["value_ma20"].transform(
        lambda s: np.where(s >= s.median(), "high", "low")
    )
    return elig


def recompute_available_at(events: pd.DataFrame, lag_days: int, holidays: set) -> pd.Series:
    """lag_days trading days after disclosure_date, for is_backfilled rows
    (100% of the dataset today -- see prereg). live rows keep available_at
    as-is (none exist currently, kept for correctness if that changes)."""
    if lag_days == 1:
        return events["available_at"]

    cache: dict[pd.Timestamp, pd.Timestamp] = {}

    def _lag(ts: pd.Timestamp) -> pd.Timestamp:
        if ts in cache:
            return cache[ts]
        cur = pd.Timestamp(ts)
        for _ in range(lag_days):
            cur = next_trading_day(cur, holidays=holidays)
        cache[ts] = cur
        return cur

    disclosure_date = pd.to_datetime(events["disclosure_date"])
    lagged = disclosure_date.apply(_lag)
    return np.where(events["is_backfilled"].astype(bool), lagged, events["available_at"])


def load_signal_events(events_all: pd.DataFrame, event_type: str, direction: str, lag_days: int, holidays: set) -> pd.DataFrame:
    mask = (events_all["event_type"] == event_type) & (events_all["direction"] == direction)
    sub = events_all.loc[mask, ["symbol", "disclosure_date", "is_backfilled", "available_at"]].copy()
    sub["available_at"] = recompute_available_at(sub, lag_days, holidays)
    sub["available_at"] = pd.to_datetime(sub["available_at"])
    return sub.dropna(subset=["available_at"])


def build_active_flags(signal_events: pd.DataFrame, trading_days: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Per symbol, a boolean array over trading_days marking the union of
    all [available_at, available_at+19] windows for that symbol's events."""
    n = len(trading_days)
    diffs: dict[str, np.ndarray] = {}
    td_values = trading_days.values
    for symbol, grp in signal_events.groupby("symbol"):
        arr = diffs.setdefault(symbol, np.zeros(n + 1, dtype=np.int32))
        for at in grp["available_at"]:
            start_idx = int(np.searchsorted(td_values, np.datetime64(at), side="left"))
            if start_idx >= n:
                continue
            end_idx = min(start_idx + SIGNAL_WINDOW_DAYS, n)
            arr[start_idx] += 1
            arr[end_idx] -= 1
    active: dict[str, np.ndarray] = {}
    for symbol, diff in diffs.items():
        cum = np.cumsum(diff[:-1])
        active[symbol] = cum > 0
    return active


def attach_active_column(eligible: pd.DataFrame, active_flags: dict[str, np.ndarray], col: str) -> pd.DataFrame:
    out = eligible.copy()
    result = np.zeros(len(out), dtype=bool)
    for symbol, grp_idx in out.groupby("symbol").groups.items():
        arr = active_flags.get(symbol)
        if arr is None:
            continue
        idx = out.loc[grp_idx, "day_idx"].to_numpy()
        result[out.index.get_indexer(grp_idx)] = arr[idx]
    out[col] = result
    return out


def _row_indices_by_day(day_idx: np.ndarray, day_min: int, day_max: int) -> list[np.ndarray]:
    """row positions bucketed by day_idx, dense array indexed by (day - day_min)
    for O(1) lookup during bootstrap resampling."""
    n_days = day_max - day_min + 1
    buckets: list[list[int]] = [[] for _ in range(n_days)]
    for pos, d in enumerate(day_idx):
        buckets[d - day_min].append(pos)
    return [np.asarray(b, dtype=np.int64) for b in buckets]


def block_bootstrap_lift(defined: pd.DataFrame, active_col: str, n_bootstrap: int = N_BOOTSTRAP, block_size: int = BLOCK_SIZE, random_state: int = RANDOM_STATE) -> dict:
    """defined: rows with non-NaN event. Block bootstrap over day_idx blocks
    of `block_size` trading days (resample which BLOCKS of trading days are
    included, not individual (symbol,day) rows) -- vectorized with numpy for
    speed (this repo's existing bootstrap-by-pandas-concat pattern was too
    slow at N_BOOTSTRAP=1000 x dozens of calls in this script)."""
    if defined.empty:
        return {"lift": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n": 0, "base_rate": np.nan, "n_active": 0}

    day_idx = defined["day_idx"].to_numpy()
    event = defined["event"].to_numpy(dtype=float)
    active = defined[active_col].to_numpy(dtype=bool)

    n_active_events = int(active.sum())
    base_rate = float(event.mean())
    active_rate = float(event[active].mean()) if n_active_events > 0 else np.nan
    point_lift = active_rate / base_rate if base_rate > 0 and n_active_events > 0 else np.nan

    day_min, day_max = int(day_idx.min()), int(day_idx.max())
    n_days_span = day_max - day_min + 1
    n_blocks = int(np.ceil(n_days_span / block_size))
    block_starts_available = (
        np.arange(day_min, day_max - block_size + 2) if n_days_span >= block_size else np.array([day_min])
    )

    buckets = _row_indices_by_day(day_idx, day_min, day_max)
    n_days = len(buckets)

    rng = np.random.default_rng(random_state)
    lifts = np.full(n_bootstrap, np.nan)
    for i in range(n_bootstrap):
        chosen_starts = rng.choice(block_starts_available, size=n_blocks, replace=True)
        rows: list[np.ndarray] = []
        for s in chosen_starts:
            s0 = s - day_min
            s1 = min(s0 + block_size, n_days)
            for bucket in buckets[s0:s1]:
                if bucket.size:
                    rows.append(bucket)
        if not rows:
            continue
        idx = np.concatenate(rows)
        b_base = event[idx].mean()
        act_mask = active[idx]
        if not act_mask.any() or b_base == 0 or np.isnan(b_base):
            continue
        lifts[i] = event[idx][act_mask].mean() / b_base

    valid = lifts[~np.isnan(lifts)]
    ci_lo, ci_hi = (float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5))) if len(valid) > 0 else (np.nan, np.nan)
    return {
        "lift": point_lift,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "n_bootstrap_valid": int(len(valid)),
        "n": int(len(defined)),
        "n_active": n_active_events,
        "base_rate": base_rate,
        "active_rate": active_rate,
    }


def classify(lift_by_period: dict[str, dict]) -> str:
    conclusive = {p: r for p, r in lift_by_period.items() if r["n_events_defined"] >= MIN_EVENTS_FOR_CONCLUSION}
    if len(conclusive) == 0:
        return "STRUCTURALLY_INCONCLUSIVE (0/3 periods have >=30 events)"
    same_sign_gt1 = sum(1 for r in conclusive.values() if r["lift"] > 1)
    pooled = lift_by_period.get("pooled", {})
    if pooled.get("ci_lo", np.nan) > 1.5 and same_sign_gt1 == len(conclusive) and len(conclusive) == 3:
        return "PASS"
    if pooled.get("ci_lo", np.nan) > 1.0 and same_sign_gt1 >= 2 and len(conclusive) >= 2:
        return "CANDIDATE"
    return "NEGATIVE"


def run_main_test(eligible: pd.DataFrame, signal_events_by_name: dict[str, pd.DataFrame], trading_days: pd.DatetimeIndex, lag_label: str) -> dict:
    results = {}
    for name, events in signal_events_by_name.items():
        active_flags = build_active_flags(events, trading_days)
        panel = attach_active_column(eligible, active_flags, "active")
        defined = panel.dropna(subset=["event"]).copy()

        pooled = block_bootstrap_lift(defined, "active")
        pooled["n_events_defined"] = int(defined["event"].sum())

        by_period = {"pooled": pooled}
        for pname, start, end in PERIODS:
            sub = defined[(defined["date"] >= start) & (defined["date"] < end)]
            r = block_bootstrap_lift(sub, "active")
            r["n_events_defined"] = int(sub["event"].sum())
            by_period[pname] = r

        by_liq = {}
        for grp_name in ["high", "low"]:
            sub = defined[defined["liq_group"] == grp_name]
            r = block_bootstrap_lift(sub, "active")
            r["n_events_defined"] = int(sub["event"].sum())
            by_liq[grp_name] = r

        verdict = classify(by_period)
        results[name] = {
            "lag_label": lag_label,
            "pooled": pooled,
            "by_period": by_period,
            "by_liquidity_group": by_liq,
            "verdict": verdict,
        }
        print(f"  [{lag_label}] {name}: verdict={verdict} pooled_lift={pooled['lift']:.3f} ci=[{pooled['ci_lo']:.3f},{pooled['ci_hi']:.3f}] n_active_defined={pooled['n_active']}")
    return results


def cluster_events(events: pd.DataFrame, gap_days: int, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    td_values = trading_days.values
    events = events.copy()
    events["day_idx"] = events["available_at"].apply(
        lambda t: int(np.searchsorted(td_values, np.datetime64(t), side="left"))
    )
    events = events.sort_values(["symbol", "day_idx"])
    keep_rows = []
    for symbol, grp in events.groupby("symbol"):
        grp = grp.sort_values("day_idx")
        last_kept_idx = None
        for _, row in grp.iterrows():
            if last_kept_idx is None or (row["day_idx"] - last_kept_idx) >= gap_days:
                keep_rows.append(row)
                last_kept_idx = row["day_idx"]
    return pd.DataFrame(keep_rows) if keep_rows else events.iloc[0:0]


def compute_car(clustered: pd.DataFrame, price_panel: pd.DataFrame, trading_days: pd.DatetimeIndex, horizon: int) -> pd.DataFrame:
    td_values = trading_days.values
    n = len(trading_days)
    sf = price_panel.set_index(["symbol", "date"])["close"] if "close" in price_panel.columns else None
    rows = []
    close_by_symbol = {s: g.set_index("date")["close"] for s, g in price_panel.groupby("symbol")} if "close" in price_panel.columns else None
    vnindex = price_panel[["date"]].drop_duplicates().merge(
        pd.read_parquet("data/processed/benchmark_vnindex.parquet", columns=["date", "close"]),
        on="date", how="left",
    ).set_index("date")["close"]
    for _, ev in clustered.iterrows():
        start_idx = ev["day_idx"]
        end_idx = start_idx + horizon
        if end_idx >= n:
            continue
        start_date, end_date = trading_days[start_idx], trading_days[end_idx]
        sym_close = close_by_symbol.get(ev["symbol"])
        if sym_close is None or start_date not in sym_close.index or end_date not in sym_close.index:
            continue
        if start_date not in vnindex.index or end_date not in vnindex.index:
            continue
        start_px, end_px = sym_close.loc[start_date], sym_close.loc[end_date]
        bench_start_px, bench_end_px = vnindex.loc[start_date], vnindex.loc[end_date]
        # Same non-positive-price guard as src/features/returns.py::add_returns
        # (valid_prices = out[price_col].where(out[price_col] > 0.0)) -- 387
        # rows in stock_features.parquet have close<=0 (known data quirk,
        # unrelated to this round's scope), which would otherwise produce
        # inf/nan returns and corrupt the bootstrap CI.
        if start_px <= 0 or end_px <= 0 or bench_start_px <= 0 or bench_end_px <= 0:
            continue
        stock_ret = end_px / start_px - 1.0
        bench_ret = bench_end_px / bench_start_px - 1.0
        rows.append({"symbol": ev["symbol"], "day_idx": start_idx, "car": stock_ret - bench_ret})
    return pd.DataFrame(rows)


def block_bootstrap_mean_car(car_df: pd.DataFrame, block_size: int = BLOCK_SIZE, n_bootstrap: int = N_BOOTSTRAP, random_state: int = RANDOM_STATE) -> dict:
    if car_df.empty:
        return {"mean_car": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n": 0}
    day_idx = car_df["day_idx"].to_numpy()
    car = car_df["car"].to_numpy(dtype=float)
    day_min, day_max = int(day_idx.min()), int(day_idx.max())
    n_days_span = day_max - day_min + 1
    if n_days_span < block_size:
        block_starts_available = np.array([day_min])
        n_blocks = 1
    else:
        block_starts_available = np.arange(day_min, day_max - block_size + 2)
        n_blocks = int(np.ceil(n_days_span / block_size))

    buckets = _row_indices_by_day(day_idx, day_min, day_max)
    n_days = len(buckets)
    rng = np.random.default_rng(random_state)
    means = np.full(n_bootstrap, np.nan)
    for i in range(n_bootstrap):
        starts = rng.choice(block_starts_available, size=n_blocks, replace=True)
        rows: list[np.ndarray] = []
        for s in starts:
            s0 = s - day_min
            s1 = min(s0 + block_size, n_days)
            for bucket in buckets[s0:s1]:
                if bucket.size:
                    rows.append(bucket)
        if not rows:
            continue
        idx = np.concatenate(rows)
        means[i] = car[idx].mean()
    valid = means[~np.isnan(means)]
    ci_lo, ci_hi = (float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5))) if len(valid) else (np.nan, np.nan)
    return {"mean_car": float(car_df["car"].mean()), "ci_lo": ci_lo, "ci_hi": ci_hi, "n": len(car_df)}


def main():
    print("Loading price panel + trading calendar...")
    price_panel_full = pd.read_parquet("data/processed/stock_features.parquet", columns=["symbol", "date", "close", "value_ma20", "forward_return_60d"])
    panel = load_price_panel()
    trading_days = pd.DatetimeIndex(sorted(pd.read_parquet("data/raw/index_ohlcv/VNINDEX.parquet", columns=["date"])["date"].unique()))
    eligible = build_eligible_panel(panel, trading_days)
    print(f"Eligible panel: {len(eligible)} rows, {eligible['symbol'].nunique()} symbols")

    events_all = pd.read_parquet("data/disclosure/events.parquet", columns=["symbol", "event_type", "direction", "disclosure_date", "is_backfilled", "available_at"])
    holidays = load_market_holidays()

    all_results = {"main_test": {}, "car_test": {}, "meta": {
        "eligible_panel_rows": int(len(eligible)),
        "eligible_symbols": int(eligible["symbol"].nunique()),
        "liquidity_threshold_vnd": LIQUIDITY_THRESHOLD,
        "n_bootstrap": N_BOOTSTRAP,
        "block_size_trading_days": BLOCK_SIZE,
        "random_state": RANDOM_STATE,
    }, "lineage": build_lineage()}

    for lag in [1, 3, 5]:
        lag_label = f"lag_{lag}"
        print(f"\n=== Main test, lag={lag} trading days ===")
        signal_events_by_name = {
            name: load_signal_events(events_all, etype, direction, lag, holidays)
            for name, (etype, direction) in SIGNAL_DEFS.items()
        }
        for name, ev in signal_events_by_name.items():
            print(f"  {name}: {len(ev)} events")
        all_results["main_test"][lag_label] = run_main_test(eligible, signal_events_by_name, trading_days, lag_label)

    print("\n=== CAR secondary test (lag=1 only) ===")
    signal_events_lag1 = {
        name: load_signal_events(events_all, etype, direction, 1, holidays)
        for name, (etype, direction) in SIGNAL_DEFS.items()
    }
    for name, events in signal_events_lag1.items():
        clustered = cluster_events(events, CAR_CLUSTER_GAP_DAYS, trading_days)
        car_by_horizon = {}
        for h in CAR_HORIZONS:
            car_df = compute_car(clustered, price_panel_full, trading_days, h)
            res = block_bootstrap_mean_car(car_df)
            car_by_horizon[f"car_{h}d"] = res
            print(f"  {name} CAR_{h}d: mean={res['mean_car']:.4f} ci=[{res['ci_lo']:.4f},{res['ci_hi']:.4f}] n={res['n']}")
        all_results["car_test"][name] = {
            "n_raw_events": int(len(events)),
            "n_clustered_events": int(len(clustered)),
            "by_horizon": car_by_horizon,
        }

    out_path = Path("data/disclosure/event_study_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
