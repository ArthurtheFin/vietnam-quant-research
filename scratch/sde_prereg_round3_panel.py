"""SDE_SCORING_PREREG.md Vòng 3, NV1 -- point-in-time re-scoring panel.

Runs the UNMODIFIED stock-decision-engine pipeline (features.enrich +
simulation.bootstrap_monte_carlo + scoring.score_decision, byte-identical
to what the notebook calls) for every (symbol, rebalance date) in the
trading_status==ACTIVE universe, at every 20-trading-day rebalance date
(matches rebalance_period=20 / mc_horizon_days=20), using exactly
lookback_days=756 rows ending at that date.

Finding #9 discipline: a symbol is only scored at a given date if it has
>=756 rows of history in data/processed/clean_daily_ohlcv.parquet as of
that date. Skipped (symbol, date) combos are counted, not silently
dropped -- see the printed summary and PANEL_SKIP_SUMMARY.

backtest evidence is passed as {"available": False} for every historical
call -- this is not a modification of the formula, it is the honest input:
data/signals/breakout_20d_trade_cards.parquet is a current snapshot only
(SDE_SCORING_PREREG.md section 3), so no point-in-time backtest evidence
ever existed for any past date. final_score is therefore the genuine
production composite with alpha's backtest.profit_factor term at its
honestly-unavailable value (0 of 20 internal points), not a redefinition.

Output: data/full_history_v2/sde_round3_panel.parquet
  columns: symbol, date, final_score, sub_market_regime, sub_trend,
  sub_momentum, sub_relative_strength, sub_risk, sub_liquidity,
  sub_simulation, sub_alpha
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
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
import sde_regenerate_gate6 as sde  # noqa: E402  (reuse _load_stock_full/_load_benchmark_full)

from src.validation.trading_status import latest_trading_status  # noqa: E402

REBALANCE_PERIOD = 20
OUT_PATH = PROJECT_ROOT / "data/full_history_v2/sde_round3_panel.parquet"
SKIP_LOG_PATH = PROJECT_ROOT / "data/full_history_v2/sde_round3_panel_skips.csv"


def main() -> None:
    cfg_base = load_config(ENGINE_ROOT / "config.yaml", PROJECT_ROOT)
    lookback_days = cfg_base["lookback_days"]

    clean_path = _official_clean_ohlcv_path(PROJECT_ROOT)
    print(f"Loading {clean_path.relative_to(PROJECT_ROOT)} ...")
    all_stock = sde._load_stock_full(clean_path)
    all_bench = sde._load_benchmark_full(PROJECT_ROOT, "VNINDEX")

    active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])
    all_stock = all_stock[all_stock["symbol"].astype(str).str.upper().isin(active_symbols)]
    print(f"ACTIVE universe: {len(active_symbols)} symbols")

    all_dates = sorted(all_stock["date"].unique())
    rebalance_dates = all_dates[::REBALANCE_PERIOD]
    print(f"Trading calendar: {len(all_dates)} dates [{all_dates[0]} .. {all_dates[-1]}]")
    print(f"Rebalance dates (every {REBALANCE_PERIOD}d): {len(rebalance_dates)}")

    stock_by_symbol = {sym: g.sort_values("date").reset_index(drop=True) for sym, g in all_stock.groupby("symbol")}

    rows: list[dict] = []
    skip_short_history = 0
    skip_error = 0
    scored = 0
    first_valid_date = None
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
                if skip_error <= 20:
                    print(f"  ERROR {sym} {rd.date()}: {exc}")
                continue

            actual_date = pd.Timestamp(metrics["date"])
            if first_valid_date is None:
                first_valid_date = actual_date
            sub = decision["sub_scores"].set_index("component")["score"]
            rows.append(
                {
                    "symbol": sym,
                    "date": actual_date,
                    "final_score": decision["final_score"],
                    "sub_market_regime": sub.get("market_regime"),
                    "sub_trend": sub.get("trend"),
                    "sub_momentum": sub.get("momentum"),
                    "sub_relative_strength": sub.get("relative_strength"),
                    "sub_risk": sub.get("risk"),
                    "sub_liquidity": sub.get("liquidity"),
                    "sub_simulation": sub.get("simulation"),
                    "sub_alpha": sub.get("alpha"),
                }
            )
            scored += 1

        elapsed = time.time() - t0
        print(
            f"[{elapsed:6.0f}s] rebalance {di+1}/{len(rebalance_dates)} ({rd.date()}): "
            f"scored={scored} skip_short_history={skip_short_history} skip_error={skip_error}"
        )
        sys.stdout.flush()

    panel = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUT_PATH, index=False)

    pd.DataFrame(
        [
            {"metric": "total_rebalance_dates", "value": len(rebalance_dates)},
            {"metric": "active_universe_symbols", "value": len(active_symbols)},
            {"metric": "scored_symbol_date_rows", "value": scored},
            {"metric": "skipped_short_history_rows", "value": skip_short_history},
            {"metric": "skipped_error_rows", "value": skip_error},
            {"metric": "first_valid_scored_date", "value": str(first_valid_date.date()) if first_valid_date is not None else None},
            {"metric": "lookback_days_required", "value": lookback_days},
        ]
    ).to_csv(SKIP_LOG_PATH, index=False)

    print(f"\nDONE in {time.time()-t0:.0f}s. Panel: {len(panel)} rows -> {OUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"First valid scored date: {first_valid_date}")
    print(f"Skipped (insufficient {lookback_days}-day history): {skip_short_history}")
    print(f"Skipped (error): {skip_error}")


if __name__ == "__main__":
    main()
