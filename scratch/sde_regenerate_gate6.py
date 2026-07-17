"""NV2 (round: sửa chân dữ liệu SDE + regenerate + prereg) -- regenerate the
20 existing stock-decision-engine analysis runs on the now-clean data
source (data/processed/clean_daily_ohlcv.parquet, regenerated from
full_history_v2 since gate #6, commit 28b9f60), as-of the SAME date each
old run used, so the comparison isolates the data fix's effect and nothing
else (not ~3 weeks of new price action).

Does NOT touch stock-decision-engine/src/scoring.py or config.yaml -- same
formula/weights/thresholds as before (CLAUDE.md rule 10). Only the input
price series changes.

Usage: python scratch/sde_regenerate_gate6.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PROJECT_ROOT / "stock-decision-engine"
SRC = ENGINE_ROOT / "src"
for p in (str(SRC), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from data import _normalize, _official_clean_ohlcv_path, load_backtest_evidence, load_config  # noqa: E402
from features import enrich  # noqa: E402
from report import save_outputs  # noqa: E402
from scoring import score_decision  # noqa: E402
from simulation import bootstrap_monte_carlo  # noqa: E402
from visualization import save_all_charts  # noqa: E402

OUTPUTS_DIR = ENGINE_ROOT / "outputs"
ARCHIVE_DIR = OUTPUTS_DIR / "archive_pre_gate6_fix_2026-07-17"

# The 20 existing (ticker, as-of date) runs, read off the committed output
# filenames before this script touches anything.
RUNS = [
    ("ACB", "2026-06-26"),
    ("BID", "2026-06-26"),
    ("BID", "2026-06-30"),
    ("BMP", "2026-06-26"),
    ("CTG", "2026-06-26"),
    ("GEX", "2026-06-30"),
    ("GEX", "2026-07-06"),
    ("HDB", "2026-07-02"),
    ("HPG", "2026-06-26"),
    ("POW", "2026-06-26"),
    ("POW", "2026-07-06"),
    ("SSI", "2026-06-26"),
    ("STB", "2026-06-26"),
    ("STB", "2026-07-02"),
    ("TPB", "2026-06-26"),
    ("VCB", "2026-06-30"),
    ("VIB", "2026-06-26"),
    ("VIX", "2026-07-06"),
    ("VPB", "2026-07-06"),
    ("VPL", "2026-06-24"),
]

CORRUPTED_TICKERS = {"BID", "HDB", "HPG", "TPB", "VCB"}

# Discovered while validating this script (not in the original audit):
# row count each ticker had in the PRE-BACKFILL clean_daily_ohlcv.parquet
# (data/quarantine_existing_v1/), i.e. what stock-decision-engine's
# lookback_days=756 window actually got at run time, before the full
# 2020-2026 backfill landed (2026-07-10, four days before the last of
# these 20 runs). Below 756 means the config's intended 3-year window was
# silently truncated to whatever history existed -- a second, independent
# data-quality issue from the raw/adjusted-close corruption (finding #1),
# affecting the *_alpha_/*_risk_ full-window statistics (Sharpe, Sortino,
# Calmar, Jensen alpha, information ratio, max_drawdown, CVaR, skewness)
# for most of these tickers regardless of whether their prices were
# corrupted.
OLD_ROWS_PRE_BACKFILL = {
    "ACB": 345, "BID": 871, "BMP": 871, "CTG": 1622, "GEX": 345, "HDB": 871,
    "HPG": 871, "POW": 295, "SSI": 328, "STB": 332, "TPB": 871, "VCB": 871,
    "VIB": 1615, "VIX": 295, "VPB": 1622, "VPL": 288,
}


def _as_of(df: pd.DataFrame, as_of_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
    out = df[df["date"] <= as_of_date].sort_values("date")
    return out.tail(lookback_days).reset_index(drop=True) if lookback_days else out.reset_index(drop=True)


def _load_stock_full(path: Path) -> pd.DataFrame:
    """Mirrors data.py:load_stock_ohlcv's normalization exactly (reuses the
    same private _normalize helper) minus the ticker filter and lookback
    truncation, which this script applies itself with an as-of date."""
    return _normalize(pd.read_parquet(path))


def _load_benchmark_full(root: Path, symbol: str = "VNINDEX") -> pd.DataFrame:
    """Mirrors data.py:load_benchmark_ohlcv's normalization exactly (same
    path-search order and column-fallback rules) minus the lookback
    truncation."""
    slug = symbol.lower()
    paths = [
        root / f"data/processed/benchmark_{slug}.parquet",
        root / "data/processed/index_features.parquet",
        root / f"data/raw/index_ohlcv/{symbol}.parquet",
        _official_clean_ohlcv_path(root),
    ]
    for path in paths:
        if not path.exists():
            continue
        df = _normalize(pd.read_parquet(path), symbol)
        if "symbol" in df.columns:
            df = df[df["symbol"].astype(str).str.upper().isin([symbol, slug.upper()])]
        if df.empty:
            continue
        if not {"open", "high", "low"}.issubset(df.columns):
            df["open"] = df.get("open", df["close"])
            df["high"] = df.get("high", df["close"])
            df["low"] = df.get("low", df["close"])
        df["volume"] = df.get("volume", df.get("totalmatchvol", 0.0))
        df["value"] = df.get("value", df["close"] * df["volume"])
        return df
    raise FileNotFoundError(f"Benchmark {symbol} not found under any of: {[str(p) for p in paths]}")


def _parse_old_summary(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    score_m = re.search(r"Final Score:\s*([\d.]+)/100", text)
    decision_m = re.search(r"Decision:\s*(.+)", text)
    return {
        "final_score": score_m.group(1) if score_m else None,
        "decision": decision_m.group(1).strip() if decision_m else None,
    }


def main() -> None:
    cfg_base = load_config(ENGINE_ROOT / "config.yaml", PROJECT_ROOT)
    lookback_days = cfg_base["lookback_days"]

    clean_path = _official_clean_ohlcv_path(PROJECT_ROOT)
    print(f"Reading stock OHLCV from {clean_path.relative_to(PROJECT_ROOT)} (dataset_config.OFFICIAL_CLEAN_OHLCV_PATH)")
    all_stock = _load_stock_full(clean_path)
    all_bench = _load_benchmark_full(PROJECT_ROOT, "VNINDEX")

    # 1) Archive the 20 old runs' files (all file types) before anything is overwritten.
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived = []
    for ticker, date in RUNS:
        prefix = f"{ticker}_{date}"
        for f in OUTPUTS_DIR.glob(f"{prefix}_*"):
            target = ARCHIVE_DIR / f.name
            f.rename(target)
            archived.append(f.name)
    print(f"Archived {len(archived)} pre-fix files into {ARCHIVE_DIR.relative_to(PROJECT_ROOT)}")

    # 2) Regenerate, as-of the same date, on the now-clean data source.
    comparison_rows = []
    for ticker, date_str in RUNS:
        as_of = pd.Timestamp(date_str)
        stock = _as_of(all_stock[all_stock["symbol"].astype(str).str.upper() == ticker], as_of, lookback_days)
        bench = _as_of(all_bench, as_of, lookback_days)
        if stock.empty or bench.empty:
            print(f"SKIP {ticker} {date_str}: no rows as-of this date in current data")
            continue

        cfg = dict(cfg_base)
        cfg["ticker"] = ticker
        cfg["benchmark"] = "VNINDEX"
        backtest = load_backtest_evidence(ticker, PROJECT_ROOT)

        stock_f, bench_f, rs, roll, metrics = enrich(stock, bench, cfg)
        mc = bootstrap_monte_carlo(stock_f, metrics, cfg)
        decision = score_decision(metrics, mc.summary, backtest, cfg)

        actual_date = pd.Timestamp(metrics["date"]).date().isoformat()
        if actual_date != date_str:
            print(f"WARNING {ticker}: requested as-of {date_str}, data's last available date is {actual_date}")

        save_all_charts(stock_f, bench_f, rs, roll, mc.paths, metrics, decision, OUTPUTS_DIR, ticker)
        save_outputs(OUTPUTS_DIR, ticker, metrics, decision, mc.summary, backtest, root=PROJECT_ROOT)

        old_summary_path = ARCHIVE_DIR / f"{ticker}_{date_str}_decision_summary.txt"
        old = _parse_old_summary(old_summary_path) if old_summary_path.exists() else {"final_score": None, "decision": None}
        old_scores_path = ARCHIVE_DIR / f"{ticker}_{date_str}_sub_scores.csv"
        old_scores = pd.read_csv(old_scores_path).set_index("component")["score"] if old_scores_path.exists() else pd.Series(dtype=float)
        new_scores = decision["sub_scores"].set_index("component")["score"]

        old_rows = OLD_ROWS_PRE_BACKFILL.get(ticker)
        row = {
            "ticker": ticker,
            "date": date_str,
            "price_corrupted": ticker in CORRUPTED_TICKERS,
            "old_rows_pre_backfill": old_rows,
            "window_truncated": bool(old_rows is not None and old_rows < lookback_days),
            "final_score_old": old["final_score"],
            "final_score_new": decision["final_score"],
            "decision_old": old["decision"],
            "decision_new": decision["decision"],
            "decision_flipped": (old["decision"] is not None) and (old["decision"] != decision["decision"]),
        }
        for component in new_scores.index:
            row[f"sub_{component}_old"] = old_scores.get(component)
            row[f"sub_{component}_new"] = new_scores.get(component)
        comparison_rows.append(row)
        print(f"OK {ticker} {date_str}: final_score {row['final_score_old']} -> {row['final_score_new']}, decision {row['decision_old']!r} -> {row['decision_new']!r}")

    comparison = pd.DataFrame(comparison_rows)
    out_path = ENGINE_ROOT / "GATE6_REGEN_COMPARISON.csv"
    comparison.to_csv(out_path, index=False)
    print(f"\nWrote comparison table: {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
