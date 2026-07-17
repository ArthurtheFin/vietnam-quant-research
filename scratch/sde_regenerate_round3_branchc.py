"""SDE_SCORING_PREREG.md Vòng 3, NV2 -- thi hành Nhánh C: regenerate cùng
20 (ticker, as-of date) runs từ round trước (scratch/sde_regenerate_gate6.py),
lần này trên scoring.py đã gỡ final_score/decision (Nhánh C). Cùng as-of
date như trước (không phải "chạy hôm nay") để tách riêng hiệu ứng đổi công
thức, không lẫn với biến động giá 3 tuần qua.

Archive các file *_decision_summary.txt/_sub_scores.csv (từ round trước --
gate-6-fixed data, công thức cũ) trước khi ghi đè. Bảng so sánh cuối cùng:
final_score/decision CŨ (đã có bằng chứng dữ liệu sạch) vs. trạng thái MỚI
(không còn composite/decision nào, chỉ còn facts).

Usage: python scratch/sde_regenerate_round3_branchc.py
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
sys.path.insert(0, str(PROJECT_ROOT / "scratch"))

from data import _normalize, load_backtest_evidence, load_config, _official_clean_ohlcv_path  # noqa: E402
from features import enrich  # noqa: E402
from report import save_outputs  # noqa: E402
from scoring import build_facts_table  # noqa: E402
from simulation import bootstrap_monte_carlo  # noqa: E402
from visualization import save_all_charts  # noqa: E402

OUTPUTS_DIR = ENGINE_ROOT / "outputs"
ARCHIVE_DIR = OUTPUTS_DIR / "archive_pre_round3_branchc_2026-07-17"

# Same 20 (ticker, as-of date) runs as scratch/sde_regenerate_gate6.py
# (RUNS constant there) -- inlined rather than imported, since importing
# that module re-executes its own `from scoring import score_decision`
# (removed in Branch C) at import time.
RUNS = [
    ("ACB", "2026-06-26"), ("BID", "2026-06-26"), ("BID", "2026-06-30"),
    ("BMP", "2026-06-26"), ("CTG", "2026-06-26"), ("GEX", "2026-06-30"),
    ("GEX", "2026-07-06"), ("HDB", "2026-07-02"), ("HPG", "2026-06-26"),
    ("POW", "2026-06-26"), ("POW", "2026-07-06"), ("SSI", "2026-06-26"),
    ("STB", "2026-06-26"), ("STB", "2026-07-02"), ("TPB", "2026-06-26"),
    ("VCB", "2026-06-30"), ("VIB", "2026-06-26"), ("VIX", "2026-07-06"),
    ("VPB", "2026-07-06"), ("VPL", "2026-06-24"),
]


def _as_of(df: pd.DataFrame, as_of_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
    out = df[df["date"] <= as_of_date].sort_values("date")
    return out.tail(lookback_days).reset_index(drop=True) if lookback_days else out.reset_index(drop=True)


def _load_stock_full(path: Path) -> pd.DataFrame:
    return _normalize(pd.read_parquet(path))


def _load_benchmark_full(root: Path, symbol: str = "VNINDEX") -> pd.DataFrame:
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
    all_stock = _load_stock_full(clean_path)
    all_bench = _load_benchmark_full(PROJECT_ROOT, "VNINDEX")

    # 1) Archive the 20 gate-6-fixed-but-old-formula runs before overwriting.
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived = []
    for ticker, date in RUNS:
        prefix = f"{ticker}_{date}"
        for f in OUTPUTS_DIR.glob(f"{prefix}_decision_summary.txt"):
            f.rename(ARCHIVE_DIR / f.name)
            archived.append(f.name)
        for f in OUTPUTS_DIR.glob(f"{prefix}_sub_scores.csv"):
            f.rename(ARCHIVE_DIR / f.name)
            archived.append(f.name)
        for f in OUTPUTS_DIR.glob(f"{prefix}_metrics.csv"):
            f.rename(ARCHIVE_DIR / f.name)
            archived.append(f.name)
    print(f"Archived {len(archived)} pre-Branch-C files into {ARCHIVE_DIR.relative_to(PROJECT_ROOT)}")

    # 2) Regenerate on the new (Branch C, no final_score/decision) formula.
    comparison_rows = []
    for ticker, date_str in RUNS:
        as_of = pd.Timestamp(date_str)
        stock = _as_of(all_stock[all_stock["symbol"].astype(str).str.upper() == ticker], as_of, lookback_days)
        bench = _as_of(all_bench, as_of, lookback_days)
        if stock.empty or bench.empty:
            print(f"SKIP {ticker} {date_str}: no rows as-of this date")
            continue

        cfg = dict(cfg_base)
        cfg["ticker"] = ticker
        cfg["benchmark"] = "VNINDEX"
        backtest = load_backtest_evidence(ticker, PROJECT_ROOT)

        stock_f, bench_f, rs, roll, metrics = enrich(stock, bench, cfg)
        mc = bootstrap_monte_carlo(stock_f, metrics, cfg)
        facts = build_facts_table(metrics, mc.summary, backtest, cfg)

        actual_date = pd.Timestamp(metrics["date"]).date().isoformat()
        if actual_date != date_str:
            print(f"WARNING {ticker}: requested as-of {date_str}, data's last available date is {actual_date}")

        save_all_charts(stock_f, bench_f, rs, roll, mc.paths, metrics, facts, OUTPUTS_DIR, ticker)
        save_outputs(OUTPUTS_DIR, ticker, metrics, facts, mc.summary, backtest, root=PROJECT_ROOT)

        old_summary_path = ARCHIVE_DIR / f"{ticker}_{date_str}_decision_summary.txt"
        old = _parse_old_summary(old_summary_path) if old_summary_path.exists() else {"final_score": None, "decision": None}

        row = {
            "ticker": ticker,
            "date": date_str,
            "final_score_old_gate6fixed": old["final_score"],
            "decision_old_gate6fixed": old["decision"],
            "final_score_new": "REMOVED (Nhánh C)",
            "decision_new": "REMOVED (Nhánh C, facts-only)",
        }
        comparison_rows.append(row)
        print(f"OK {ticker} {date_str}: old final_score={old['final_score']} decision={old['decision']!r} -> Nhánh C facts-only, no composite")

    comparison = pd.DataFrame(comparison_rows)
    out_path = ENGINE_ROOT / "ROUND3_BRANCHC_REGEN_COMPARISON.csv"
    comparison.to_csv(out_path, index=False)
    print(f"\nWrote final comparison table: {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
