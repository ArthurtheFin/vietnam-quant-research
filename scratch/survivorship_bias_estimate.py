"""EXPLORATORY -- estimate a survivorship-drift floor from
docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md's finding that S3 (sell, the H2 placebo)
shows positive CAR similar in magnitude to S1/S2 (buy). Reuses the exact
CAR/block-bootstrap machinery already validated in
scratch/disclosure_event_study.py -- no new statistical methodology, no
re-run of the locked H1/H2 test itself.

Output: docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md's numbers, plus
data/disclosure/survivorship_bias_estimate.json for lineage.
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
    RANDOM_STATE,
    SIGNAL_DEFS,
    build_eligible_panel,
    build_lineage,
    cluster_events,
    compute_car,
    load_market_holidays,
    load_price_panel,
    load_signal_events,
    block_bootstrap_mean_car,
)


def unconditional_excess_return(eligible: pd.DataFrame, price_panel_full: pd.DataFrame, trading_days: pd.DatetimeIndex, horizon: int) -> pd.DataFrame:
    """Forward excess return at `horizon` trading days for EVERY (symbol,day)
    in the eligible panel, unconditional on any disclosure event -- the
    independent cross-check the task asks for. Same direct close-price-ratio
    method as compute_car (not the pre-computed forward_return_Nd feature
    columns, which only go up to 60d and use a different corporate-action
    handling path) for exact comparability with the CAR numbers.

    Vectorized (dense per-symbol close array reindexed onto the full trading
    calendar) instead of row-by-row -- the eligible panel has ~350k rows,
    too slow to loop over in Python."""
    n = len(trading_days)
    vnindex = (
        pd.read_parquet("data/processed/benchmark_vnindex.parquet", columns=["date", "close"])
        .set_index("date")["close"]
        .reindex(trading_days)
        .to_numpy()
    )

    out_frames = []
    for symbol, grp in eligible.groupby("symbol"):
        sym_close_dense = (
            price_panel_full.loc[price_panel_full["symbol"] == symbol, ["date", "close"]]
            .set_index("date")["close"]
            .reindex(trading_days)
            .to_numpy()
        )
        day_idx = grp["day_idx"].to_numpy()
        end_idx = day_idx + horizon
        valid = end_idx < n
        day_idx, end_idx = day_idx[valid], end_idx[valid]
        if len(day_idx) == 0:
            continue
        start_px, end_px = sym_close_dense[day_idx], sym_close_dense[end_idx]
        b_start, b_end = vnindex[day_idx], vnindex[end_idx]
        ok = (
            ~np.isnan(start_px) & ~np.isnan(end_px) & ~np.isnan(b_start) & ~np.isnan(b_end)
            & (start_px > 0) & (end_px > 0) & (b_start > 0) & (b_end > 0)
        )
        if not ok.any():
            continue
        excess = (end_px[ok] / start_px[ok] - 1.0) - (b_end[ok] / b_start[ok] - 1.0)
        out_frames.append(pd.DataFrame({"symbol": symbol, "day_idx": day_idx[ok], "car": excess}))
    return pd.concat(out_frames, ignore_index=True) if out_frames else pd.DataFrame(columns=["symbol", "day_idx", "car"])


def main():
    print("Loading price panel + eligible universe (same construction as NV2)...")
    price_panel_full = pd.read_parquet(
        "data/processed/stock_features.parquet", columns=["symbol", "date", "close", "value_ma20", "forward_return_60d"]
    )
    panel = load_price_panel()
    trading_days = pd.DatetimeIndex(
        sorted(pd.read_parquet("data/raw/index_ohlcv/VNINDEX.parquet", columns=["date"])["date"].unique())
    )
    eligible = build_eligible_panel(panel, trading_days)
    print(f"Eligible panel: {len(eligible)} rows, {eligible['symbol'].nunique()} symbols")

    events_all = pd.read_parquet(
        "data/disclosure/events.parquet",
        columns=["symbol", "event_type", "direction", "disclosure_date", "is_backfilled", "available_at"],
    )
    holidays = load_market_holidays()

    results: dict = {"placebo_car": {}, "pooled_all_events_car": {}, "unconditional_excess_return": {}}

    print("\n=== Per-signal CAR (reusing NV2's exact clustered event sets, lag=1) ===")
    clustered_by_signal: dict[str, pd.DataFrame] = {}
    for name, (etype, direction) in SIGNAL_DEFS.items():
        events = load_signal_events(events_all, etype, direction, 1, holidays)
        clustered = cluster_events(events, CAR_CLUSTER_GAP_DAYS, trading_days)
        clustered_by_signal[name] = clustered
        by_h = {}
        for h in CAR_HORIZONS:
            car_df = compute_car(clustered, price_panel_full, trading_days, h)
            res = block_bootstrap_mean_car(car_df)
            by_h[f"car_{h}d"] = res
            print(f"  {name} CAR_{h}d: mean={res['mean_car']:.4f} ci=[{res['ci_lo']:.4f},{res['ci_hi']:.4f}] n={res['n']}")
        results["placebo_car"][name] = by_h

    print("\n=== Pooled: all disclosure REGISTRATION events (S1+S2+S3 clustered sets concatenated) ===")
    pooled_clustered = pd.concat(clustered_by_signal.values(), ignore_index=True)
    print(f"  pooled n (pre-CAR-window-filter) = {len(pooled_clustered)}")
    for h in CAR_HORIZONS:
        car_df = compute_car(pooled_clustered, price_panel_full, trading_days, h)
        res = block_bootstrap_mean_car(car_df)
        results["pooled_all_events_car"][f"car_{h}d"] = res
        print(f"  pooled CAR_{h}d: mean={res['mean_car']:.4f} ci=[{res['ci_lo']:.4f},{res['ci_hi']:.4f}] n={res['n']}")

    print("\n=== Independent cross-check: unconditional excess return, ALL (symbol,day) in eligible panel ===")
    for h in CAR_HORIZONS:
        uncond_df = unconditional_excess_return(eligible, price_panel_full, trading_days, h)
        res = block_bootstrap_mean_car(uncond_df)
        results["unconditional_excess_return"][f"excess_{h}d"] = res
        print(f"  unconditional excess_{h}d: mean={res['mean_car']:.4f} ci=[{res['ci_lo']:.4f},{res['ci_hi']:.4f}] n={res['n']}")

    results["meta"] = {
        "n_bootstrap": N_BOOTSTRAP,
        "block_size_trading_days": BLOCK_SIZE,
        "random_state": RANDOM_STATE,
        "car_cluster_gap_days": CAR_CLUSTER_GAP_DAYS,
        "eligible_panel_rows": int(len(eligible)),
        "eligible_symbols": int(eligible["symbol"].nunique()),
        "note": "EXPLORATORY estimate, not a confirmatory test -- see docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md",
    }
    results["lineage"] = build_lineage()

    out_path = Path("data/disclosure/survivorship_bias_estimate.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
