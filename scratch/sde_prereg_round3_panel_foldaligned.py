"""SDE_SCORING_PREREG.md Vòng 3, NV1 -- fold-aligned scoring panel for the
null test.

The main panel (scratch/sde_prereg_round3_panel.py) uses a single global
20-trading-day schedule starting 2020-01-02. run_portfolio_backtest,
called separately per fold in the null test, RECOMPUTES its own rebalance
schedule from each fold's own sliced date range (all_dates[::20] where
all_dates is local to that fold) -- a different phase than the global
schedule. Using the global-schedule panel for the null test would mean
most of run_portfolio_backtest's internally-chosen decision dates have no
matching SDE score, silently falling back to the mean-reversion default
scorer instead of testing final_score at all. This script scores SDE at
the EXACT dates run_portfolio_backtest will independently derive for each
of the 5 folds, so the null test's real_r actually uses final_score.

Same engine calls, same lookback_days=756/finding#9 discipline, same
backtest={"available": False} honesty as the main panel script -- only the
set of scored dates differs.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PROJECT_ROOT / "stock-decision-engine"
SRC = ENGINE_ROOT / "src"
for p in (str(SRC), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, str(PROJECT_ROOT / "scratch"))

from data import load_config, _official_clean_ohlcv_path  # noqa: E402
from features import enrich  # noqa: E402
from scoring import score_decision  # noqa: E402
from simulation import bootstrap_monte_carlo  # noqa: E402
import sde_regenerate_gate6 as sde  # noqa: E402

from src.validation.trading_status import latest_trading_status  # noqa: E402

OUT_PATH = PROJECT_ROOT / "data/full_history_v2/sde_round3_panel_foldaligned.parquet"

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-16"),
]
REBALANCE_PERIOD = 20


def fold_local_rebalance_dates(stock_features_dates: list[pd.Timestamp]) -> list[pd.Timestamp]:
    all_needed: set[pd.Timestamp] = set()
    for start, end in FOLDS:
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        fold_dates = sorted(d for d in stock_features_dates if ts <= d <= te)
        all_needed.update(fold_dates[::REBALANCE_PERIOD])
    return sorted(all_needed)


def main() -> None:
    cfg_base = load_config(ENGINE_ROOT / "config.yaml", PROJECT_ROOT)
    lookback_days = cfg_base["lookback_days"]

    all_stock = sde._load_stock_full(_official_clean_ohlcv_path(PROJECT_ROOT))
    all_bench = sde._load_benchmark_full(PROJECT_ROOT, "VNINDEX")

    active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])
    all_stock = all_stock[all_stock["symbol"].astype(str).str.upper().isin(active_symbols)]

    # stock_features.parquet is what run_portfolio_backtest's `features` arg
    # is actually built from (see sde_prereg_round3_ic_null.py) -- use its
    # date index, not clean_daily_ohlcv's, so the schedule matches exactly.
    sf_dates = pd.read_parquet(PROJECT_ROOT / "data/processed/stock_features.parquet", columns=["date"])
    sf_dates = sorted(pd.to_datetime(sf_dates["date"].unique()))
    rebalance_dates = fold_local_rebalance_dates(sf_dates)
    print(f"Fold-aligned rebalance dates needed: {len(rebalance_dates)}")

    stock_by_symbol = {sym: g.sort_values("date").reset_index(drop=True) for sym, g in all_stock.groupby("symbol")}

    rows: list[dict] = []
    skip_short_history = 0
    skip_error = 0
    t0 = time.time()

    for di, rd in enumerate(rebalance_dates):
        bench_as_of = all_bench[all_bench["date"] <= rd]
        if len(bench_as_of) < lookback_days:
            continue
        bench = bench_as_of.tail(lookback_days).reset_index(drop=True)

        for sym, sdf in stock_by_symbol.items():
            hist = sdf[sdf["date"] <= rd]
            if len(hist) < lookback_days:
                skip_short_history += 1
                continue
            stock = hist.tail(lookback_days).reset_index(drop=True)

            cfg = dict(cfg_base)
            cfg["ticker"] = sym
            cfg["benchmark"] = "VNINDEX"
            try:
                stock_f, bench_f, rs, roll, metrics = enrich(stock, bench, cfg)
                mc = bootstrap_monte_carlo(stock_f, metrics, cfg)
                decision = score_decision(metrics, mc.summary, {"available": False}, cfg)
            except Exception as exc:  # noqa: BLE001
                skip_error += 1
                continue

            rows.append({
                "symbol": sym,
                "date": pd.Timestamp(metrics["date"]),
                "final_score": decision["final_score"],
            })

        elapsed = time.time() - t0
        print(f"[{elapsed:6.0f}s] {di+1}/{len(rebalance_dates)} ({rd.date()}): rows_so_far={len(rows)} skip_short={skip_short_history}")
        sys.stdout.flush()

    panel = pd.DataFrame(rows)
    panel.to_parquet(OUT_PATH, index=False)
    print(f"\nDONE in {time.time()-t0:.0f}s. Fold-aligned panel: {len(panel)} rows -> {OUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Skipped (insufficient history): {skip_short_history}, errors: {skip_error}")


if __name__ == "__main__":
    main()
