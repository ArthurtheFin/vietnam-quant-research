"""NV2 -- run DISCLOSURE_PREREG_2_CLUSTER.md exactly as locked. One run,
no parameter tuning after seeing results. Tests H1 (cluster buying) and
H2 (family-related-person buying) against a matched control (DCAR),
instead of against zero, per SURVIVORSHIP_BIAS_ESTIMATE.md.

Reuses (does not redefine) cluster_events/compute_car/
block_bootstrap_mean_car/recompute_available_at from
scratch/disclosure_event_study.py and the multi_insider_cluster / role_group
classification from scratch/car_s1_autopsy.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scratch.disclosure_event_study import (
    BLOCK_SIZE,
    CAR_CLUSTER_GAP_DAYS,
    CAR_HORIZONS,
    N_BOOTSTRAP,
    PERIODS,
    RANDOM_STATE,
    block_bootstrap_mean_car,
    build_lineage,
    cluster_events,
    load_market_holidays,
    recompute_available_at,
)
from scratch.car_s1_autopsy import ROLE_GROUPS, group_role
from src.validation.trading_status import latest_trading_status

MIN_EVENTS_FOR_CONCLUSION = 30
CONTROL_WINDOW_BEFORE = 60
CONTROL_WINDOW_AFTER = 120
N_CONTROLS = 5


def load_all_disclosure_events(lag_days: int, holidays: set) -> pd.DataFrame:
    ev = pd.read_parquet(
        "data/disclosure/events.parquet",
        columns=["symbol", "disclosure_date", "is_backfilled", "available_at"],
    )
    ev["available_at"] = recompute_available_at(ev, lag_days, holidays)
    ev["available_at"] = pd.to_datetime(ev["available_at"])
    return ev.dropna(subset=["available_at"])


def load_s1_buy_events(lag_days: int, holidays: set) -> pd.DataFrame:
    ev = pd.read_parquet(
        "data/disclosure/events.parquet",
        columns=["symbol", "event_type", "direction", "person_name", "person_role", "disclosure_date", "is_backfilled", "available_at"],
    )
    mask = (ev["event_type"] == "insider_registration") & (ev["direction"] == "buy")
    sub = ev.loc[mask].copy()
    sub["available_at"] = recompute_available_at(sub, lag_days, holidays)
    sub["available_at"] = pd.to_datetime(sub["available_at"])
    return sub.dropna(subset=["available_at"])


def build_matrices(price_panel_full: pd.DataFrame, trading_days: pd.DatetimeIndex):
    close_wide = price_panel_full.pivot(index="date", columns="symbol", values="close").reindex(trading_days)
    value_wide = price_panel_full.pivot(index="date", columns="symbol", values="value_ma20").reindex(trading_days)
    symbols = list(close_wide.columns)
    close_mat = close_wide.to_numpy()
    value_mat = value_wide.to_numpy()
    vnindex = pd.read_parquet("data/processed/benchmark_vnindex.parquet", columns=["date", "close"]).set_index("date")["close"].reindex(trading_days).to_numpy()
    return symbols, close_mat, value_mat, vnindex


def build_tercile_matrix(value_mat: np.ndarray) -> np.ndarray:
    """Per trading day (row), tercile bucket (0/1/2) of value_ma20 across all
    symbols with a valid value that day. -1 = missing/not rankable."""
    n_days, n_syms = value_mat.shape
    tercile = np.full((n_days, n_syms), -1, dtype=np.int8)
    for t in range(n_days):
        row = value_mat[t, :]
        valid = ~np.isnan(row)
        if valid.sum() < 3:
            continue
        ranks = pd.qcut(row[valid], 3, labels=False, duplicates="drop")
        tercile[t, valid] = ranks
    return tercile


def build_event_flag_matrix(all_events: pd.DataFrame, symbols: list[str], trading_days: pd.DatetimeIndex) -> np.ndarray:
    n_days, n_syms = len(trading_days), len(symbols)
    sym_idx = {s: i for i, s in enumerate(symbols)}
    td_values = trading_days.values
    flag = np.zeros((n_days, n_syms), dtype=bool)
    for symbol, grp in all_events.groupby("symbol"):
        j = sym_idx.get(symbol)
        if j is None:
            continue
        idxs = np.searchsorted(td_values, grp["available_at"].to_numpy(dtype="datetime64[ns]"), side="left")
        idxs = idxs[idxs < n_days]
        flag[idxs, j] = True
    return flag


def compute_car_matrix(close_mat: np.ndarray, vnindex: np.ndarray, start_idx: int, end_idx: int) -> np.ndarray:
    """CAR at every symbol column for a fixed [start_idx, end_idx] window."""
    start_px, end_px = close_mat[start_idx, :], close_mat[end_idx, :]
    b_start, b_end = vnindex[start_idx], vnindex[end_idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        stock_ret = end_px / start_px - 1.0
    bench_ret = b_end / b_start - 1.0 if (b_start > 0 and b_end > 0 and not np.isnan(b_start) and not np.isnan(b_end)) else np.nan
    car = stock_ret - bench_ret
    invalid = (start_px <= 0) | (end_px <= 0) | np.isnan(start_px) | np.isnan(end_px)
    car[invalid] = np.nan
    return car


def main():
    print("Loading price matrices + trading calendar...")
    price_panel_full = pd.read_parquet(
        "data/processed/stock_features.parquet", columns=["symbol", "date", "close", "value_ma20"]
    )
    trading_days = pd.DatetimeIndex(
        sorted(pd.read_parquet("data/raw/index_ohlcv/VNINDEX.parquet", columns=["date"])["date"].unique())
    )
    n_days = len(trading_days)
    symbols, close_mat, value_mat, vnindex = build_matrices(price_panel_full, trading_days)
    sym_idx = {s: i for i, s in enumerate(symbols)}
    print(f"Symbols: {len(symbols)}, trading days: {n_days}")

    print("Building tercile matrix (value_ma20, per trading day)...")
    tercile_mat = build_tercile_matrix(value_mat)

    active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])
    print(f"ACTIVE symbols (current snapshot): {len(active_symbols)}")

    holidays = load_market_holidays()

    all_results = {"meta": {
        "n_bootstrap": N_BOOTSTRAP, "block_size_trading_days": BLOCK_SIZE, "random_state": RANDOM_STATE,
        "n_controls": N_CONTROLS, "control_window_before": CONTROL_WINDOW_BEFORE, "control_window_after": CONTROL_WINDOW_AFTER,
    }, "by_lag": {}}

    for lag in [1, 3, 5]:
        lag_label = f"lag_{lag}"
        print(f"\n{'='*30} lag={lag} trading days {'='*30}")

        all_events = load_all_disclosure_events(lag, holidays)
        event_flag_mat = build_event_flag_matrix(all_events, symbols, trading_days)
        cum_flag = np.cumsum(event_flag_mat.astype(np.int32), axis=0)  # (n_days, n_syms)

        s1_raw = load_s1_buy_events(lag, holidays)
        td_values = trading_days.values
        s1_raw = s1_raw.copy()
        s1_raw["day_idx"] = np.searchsorted(td_values, s1_raw["available_at"].to_numpy(dtype="datetime64[ns]"), side="left")

        clustered = cluster_events(
            s1_raw[["symbol", "disclosure_date", "is_backfilled", "available_at", "person_name", "person_role"]],
            CAR_CLUSTER_GAP_DAYS, trading_days,
        )
        clustered = clustered.reset_index(drop=True)
        print(f"Clustered S1 buy events: {len(clustered)}")

        # classify groups (reuse exact car_s1_autopsy.py logic)
        raw_by_symbol = {s: g for s, g in s1_raw.groupby("symbol")}

        def n_distinct_in_window(row):
            grp = raw_by_symbol.get(row["symbol"])
            if grp is None:
                return 1
            in_window = grp[(grp["day_idx"] >= row["day_idx"]) & (grp["day_idx"] < row["day_idx"] + CAR_CLUSTER_GAP_DAYS)]
            return in_window["person_name"].nunique()

        clustered["day_idx"] = np.searchsorted(td_values, clustered["available_at"].to_numpy(dtype="datetime64[ns]"), side="left")
        clustered["n_distinct_insiders_in_window"] = clustered.apply(n_distinct_in_window, axis=1)
        clustered["is_cluster"] = clustered["n_distinct_insiders_in_window"] >= 2
        clustered["role_group"] = clustered["person_role"].apply(group_role)
        clustered["is_family"] = clustered["role_group"] == "Người liên quan (gia đình)"
        clustered["group"] = np.where(
            clustered["is_cluster"] & clustered["is_family"], "H1+H2 (cả hai)",
            np.where(clustered["is_cluster"], "H1 (cụm)", np.where(clustered["is_family"], "H2 (gia đình)", "H0 (đơn lẻ, đối chứng)")),
        )
        # H1 test population = is_cluster (regardless of family); H2 = is_family; H0 = neither
        print("Nhóm (không loại trừ lẫn nhau giữa H1/H2):")
        print(f"  H1 (cụm, is_cluster=True): {clustered['is_cluster'].sum()}")
        print(f"  H2 (gia đình, is_family=True): {clustered['is_family'].sum()}")
        print(f"  H0 (đơn lẻ, không cụm không gia đình): {(~clustered['is_cluster'] & ~clustered['is_family']).sum()}")

        rng = np.random.default_rng(RANDOM_STATE)
        clustered = clustered.sort_values(["symbol", "day_idx"]).reset_index(drop=True)
        active_mask_static = np.array([s in active_symbols for s in symbols])

        n_controls_used = []
        n_dropped_zero_controls = 0
        dcar_rows = []  # per event, per horizon
        for _, ev in clustered.iterrows():
            t = int(ev["day_idx"])
            i_sym = ev["symbol"]
            j_event = sym_idx.get(i_sym)
            if j_event is None or t >= n_days:
                n_dropped_zero_controls += 1
                continue
            tercile_i = tercile_mat[t, j_event]
            if tercile_i < 0:
                n_dropped_zero_controls += 1
                continue

            lo = max(t - CONTROL_WINDOW_BEFORE, 0)
            hi = min(t + CONTROL_WINDOW_AFTER, n_days - 1)
            window_count = cum_flag[hi, :] - (cum_flag[lo - 1, :] if lo > 0 else 0)
            quiet_mask = window_count == 0

            same_tercile_mask = tercile_mat[t, :] == tercile_i
            candidate_mask = same_tercile_mask & quiet_mask & active_mask_static
            candidate_mask[j_event] = False
            candidate_idx = np.where(candidate_mask)[0]

            if len(candidate_idx) == 0:
                n_dropped_zero_controls += 1
                continue
            n_pick = min(N_CONTROLS, len(candidate_idx))
            chosen = rng.choice(candidate_idx, size=n_pick, replace=False)
            n_controls_used.append(n_pick)

            for h in CAR_HORIZONS:
                end_idx = t + h
                if end_idx >= n_days:
                    continue
                car_all = compute_car_matrix(close_mat, vnindex, t, end_idx)
                car_event = car_all[j_event]
                car_controls = car_all[chosen]
                if np.isnan(car_event) or np.all(np.isnan(car_controls)):
                    continue
                dcar = car_event - np.nanmean(car_controls)
                dcar_rows.append({
                    "symbol": i_sym, "day_idx": t, "horizon": h, "dcar": dcar,
                    "group": ev["group"], "is_cluster": ev["is_cluster"], "is_family": ev["is_family"],
                })

        dcar_df = pd.DataFrame(dcar_rows)
        print(f"Events dropped (no valid control): {n_dropped_zero_controls}")
        print(f"Mean controls used per event: {np.mean(n_controls_used) if n_controls_used else float('nan'):.2f} (min={min(n_controls_used) if n_controls_used else 'NA'})")

        lag_result = {"n_events_total": int(len(clustered)), "n_dropped_no_control": int(n_dropped_zero_controls), "groups": {}}

        for group_name, mask_fn in [
            ("H1_cluster", lambda d: d["is_cluster"]),
            ("H2_family", lambda d: d["is_family"]),
            ("H0_baseline", lambda d: (~d["is_cluster"]) & (~d["is_family"])),
        ]:
            group_result = {}
            for h in CAR_HORIZONS:
                sub_h = dcar_df[(dcar_df["horizon"] == h) & mask_fn(dcar_df)]
                n_pooled = len(sub_h)
                print(f"  [{lag_label}] {group_name} h={h}: N(DCAR defined)={n_pooled}")
                if n_pooled == 0:
                    group_result[f"h{h}"] = {"pooled": {"mean_car": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n": 0}, "by_period": {}}
                    continue
                pooled_res = block_bootstrap_mean_car(sub_h.rename(columns={"dcar": "car"})[["day_idx", "car"]])
                by_period = {}
                for pname, start, end in PERIODS:
                    events_in_period = clustered[(clustered["available_at"] >= start) & (clustered["available_at"] < end)]
                    idx_in_period = set(zip(events_in_period["symbol"], events_in_period["day_idx"]))
                    sub_p = sub_h[sub_h.apply(lambda r: (r["symbol"], r["day_idx"]) in idx_in_period, axis=1)]
                    if len(sub_p) == 0:
                        by_period[pname] = {"mean_car": np.nan, "n": 0}
                        continue
                    by_period[pname] = {"mean_car": float(sub_p["dcar"].mean()), "n": int(len(sub_p))}
                group_result[f"h{h}"] = {"pooled": pooled_res, "by_period": by_period}
            lag_result["groups"][group_name] = group_result

        # verdicts (per horizon-60/120-and-period rule)
        for group_name in ["H1_cluster", "H2_family", "H0_baseline"]:
            g = lag_result["groups"][group_name]
            n60 = g["h60"]["pooled"]["n"]
            n120 = g["h120"]["pooled"]["n"]
            if min(n60, n120) < MIN_EVENTS_FOR_CONCLUSION:
                verdict = f"INSUFFICIENT_N (n60={n60}, n120={n120} < {MIN_EVENTS_FOR_CONCLUSION})"
            else:
                ci_lo_60 = g["h60"]["pooled"]["ci_lo"]
                ci_lo_120 = g["h120"]["pooled"]["ci_lo"]
                both_ci_positive = (ci_lo_60 > 0) and (ci_lo_120 > 0)
                periods_positive = sum(
                    1 for pname, _, _ in PERIODS
                    if g["h60"]["by_period"].get(pname, {}).get("n", 0) >= MIN_EVENTS_FOR_CONCLUSION
                    and g["h60"]["by_period"][pname]["mean_car"] > 0
                    and g["h120"]["by_period"].get(pname, {}).get("n", 0) >= MIN_EVENTS_FOR_CONCLUSION
                    and g["h120"]["by_period"][pname]["mean_car"] > 0
                )
                verdict = "PASS" if (both_ci_positive and periods_positive >= 2) else "NEGATIVE"
            g["verdict"] = verdict
            print(f"  [{lag_label}] {group_name} VERDICT: {verdict}")

        all_results["by_lag"][lag_label] = lag_result

    all_results["lineage"] = build_lineage()
    out_path = Path("data/disclosure/prereg2_cluster_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
