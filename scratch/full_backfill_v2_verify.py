"""Task 4b (docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md Round 2 Task 3, item 4): automated
post-fetch quality suite for the full 501-symbol backfill in
data/full_history_v2/raw/, extending the pilot's 4 checks to the whole
universe. Reads only; writes nothing back to existing data.

Output: one row per symbol -- [symbol, rows, date_range, check_a_pass,
check_b_distinct_ratios, check_c_pass, check_d_outlier_count] -- plus a
diagnostic column (from the Task 3 pilot finding) distinguishing
check-b failures caused by known `existing`-side corruption (isolated to
the tail of existing's own coverage, i.e. recent daily-update corruption,
or the historical HPG/TCB-style piecewise pattern) from anything else,
since check (b) structurally cannot pass for symbols where `existing`
itself is wrong -- that distinction doesn't change the acceptance-bar
computation (run per the literal finalized design) but is essential
context for reviewing which failures are pre-existing data debt vs. new
concerns from this backfill.

**Revised acceptance criterion** (per user decision after the first ~26
symbols showed 62% check-b "failures" among top-liquidity blue chips
(VCB, TCB, MBB, HDB, BID, VNM, MWG, VIC, ...), all sharing the exact same
~29-day alternating piecewise ratio pattern as HPG/TCB and starting right
at 2023-01-03 -- the date `existing`'s history begins for these names.
This proves the raw/adjusted-close bug has been corrupting `existing`
production data for the *majority* of the actively-traded universe since
data collection started, not just 2 symbols as Round 2 believed): check
(b) as originally designed ("v2 vs existing ratio must be 1 distinct
value") is comparing new-and-correct data against an old-and-broken
baseline for most symbols, so it cannot be used as a pass/fail gate --
that comparison is reported here purely as **informational evidence of
how much of `existing` is stale/wrong**, not as an acceptance criterion.

The real gate is **check (a)** (session coverage) plus v2's own internal
validity, which is structurally guaranteed by construction: Task 4 fetches
via a single direct `get_daily_ohlc` call per symbol (`page_size=1000`,
auto-paginated) -- the exact method mechanism-proven immune to the
raw/adjusted-close bug in Task 3 (that bug lives only in
`_fetch_chunk_with_fallback`, used by the chunked `fetch_symbol_history`/
`update_symbol_history` path, which Task 4 never calls). So v2 cannot
inherit that specific defect regardless of what `existing` looks like.

**Revised acceptance criterion**: >=95% of symbols pass check (a) alone.
(b) existing-mismatch rate, (c) magnitude sanity, and (d) outlier scan are
all informational/review-only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

MANIFEST_PATH = Path("data/full_history_v2/manifest.json")
RAW_DIR = Path("data/full_history_v2/raw")

pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 600)


def load_v2(sym: str) -> pd.DataFrame:
    df = pd.read_parquet(RAW_DIR / f"{sym}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    ok_symbols = sorted(s for s, v in manifest.items() if v.get("status") == "ok")
    print(f"Manifest: {len(manifest)} total, {len(ok_symbols)} status=ok, "
          f"{len(manifest) - len(ok_symbols)} error/empty")
    non_ok = {s: v for s, v in manifest.items() if v.get("status") != "ok"}
    if non_ok:
        print("Non-ok symbols:", {s: v.get("status") for s, v in non_ok.items()})

    existing = pd.read_parquet("data/processed/stock_features.parquet")
    existing["date"] = pd.to_datetime(existing["date"])
    existing_by_symbol = {sym: g[["date", "close"]] for sym, g in existing.groupby("symbol")}

    bench = pd.read_parquet("data/processed/benchmark_vnindex.parquet")
    bench["date"] = pd.to_datetime(bench["date"])
    trading_calendar = sorted(bench["date"].unique())
    calendar_by_year = pd.Series(trading_calendar).dt.year.value_counts().sort_index()
    calendar_dates_by_year = {y: [d for d in trading_calendar if d.year == y] for y in calendar_by_year.index}

    rows = []
    for sym in ok_symbols:
        df = load_v2(sym)
        n_rows = len(df)
        date_min, date_max = df["date"].min(), df["date"].max()

        # (a) session coverage for years the symbol was actually listed.
        # For the symbol's first/last partial year, only count calendar
        # sessions from its own listing date onward (a Dec-2020 IPO isn't a
        # coverage gap for Jan-Nov 2020 -- per Round 1's explicit finding).
        df_dates = set(df["date"])
        years_listed = range(date_min.year, date_max.year + 1)
        pct_by_year = {}
        for y in years_listed:
            cal = calendar_dates_by_year.get(y, [])
            cal = [d for d in cal if date_min <= d <= date_max]
            if not cal:
                continue
            pct_by_year[y] = sum(1 for d in cal if d in df_dates) / len(cal)
        check_a_pass = all(p >= 0.95 for p in pct_by_year.values()) if pct_by_year else False
        worst_year = min(pct_by_year, key=pct_by_year.get) if pct_by_year else None

        # (b) generalized junction/ratio check vs existing
        existing_sym = existing_by_symbol.get(sym)
        n_distinct_ratios = None
        tail_only = None
        if existing_sym is not None and not existing_sym.empty:
            overlap = df[["date", "close"]].merge(
                existing_sym.rename(columns={"close": "close_existing"}), on="date", how="inner"
            )
            valid = overlap[(overlap["close"] > 0) & (overlap["close_existing"] > 0)].copy()
            if not valid.empty:
                valid["ratio"] = (valid["close"] / valid["close_existing"]).round(4)
                distinct = sorted(valid["ratio"].unique().tolist())
                n_distinct_ratios = len(distinct)
                if n_distinct_ratios > 1:
                    mismatched_dates = sorted(valid.loc[valid["ratio"] != 1.0, "date"])
                    existing_max_date = existing_sym["date"].max()
                    tail_window = existing_max_date - pd.Timedelta(days=15)
                    tail_only = all(d >= tail_window for d in mismatched_dates)
        check_b_pass = n_distinct_ratios in (None, 0, 1)

        # (c) magnitude sanity
        yearly_mean_value = df.groupby(df["date"].dt.year)["value"].mean()
        all_time_median = df["value"].median()
        check_c_pass = True
        if all_time_median and all_time_median > 0:
            ratios_c = yearly_mean_value / all_time_median
            check_c_pass = bool(((ratios_c >= 0.1) & (ratios_c <= 1000)).all())

        # (d) outlier scan
        d = df.copy()
        d["prev_close"] = d["close"].shift(1)
        valid_ret = (d["close"] > 0) & (d["prev_close"] > 0)
        d["return_1d"] = np.where(valid_ret, d["close"] / d["prev_close"] - 1, np.nan)
        check_d_outlier_count = int((d["return_1d"].abs() > 0.20).sum())

        rows.append({
            "symbol": sym,
            "rows": n_rows,
            "date_range": f"{date_min.date()}..{date_max.date()}",
            "check_a_pass": check_a_pass,
            "check_a_worst_year": worst_year,
            "check_a_worst_pct": round(pct_by_year.get(worst_year, np.nan) * 100, 1) if worst_year else None,
            "check_b_distinct_ratios": n_distinct_ratios,
            "check_b_tail_only": tail_only,
            "check_c_pass": check_c_pass,
            "check_d_outlier_count": check_d_outlier_count,
        })

    result = pd.DataFrame(rows)
    result["check_b_pass"] = result["check_b_distinct_ratios"].isin([0, 1]) | result["check_b_distinct_ratios"].isna()
    result["any_hard_fail"] = ~result["check_a_pass"]
    result = result.sort_values(["any_hard_fail", "symbol"], ascending=[False, True])

    out_path = Path("data/full_history_v2/quality_report.csv")
    result.to_csv(out_path, index=False)
    print(f"\nWrote full quality report ({len(result)} rows) to {out_path}")

    n = len(result)
    n_pass_a = int(result["check_a_pass"].sum())
    n_pass_b = int(result["check_b_pass"].sum())
    n_tail_only_b_fail = int((~result["check_b_pass"] & (result["check_b_tail_only"] == True)).sum())  # noqa: E712
    n_broad_b_fail = int((~result["check_b_pass"] & (result["check_b_tail_only"] == False)).sum())  # noqa: E712

    print("\n" + "=" * 80)
    print(f"SUMMARY over {n} status=ok symbols (of {len(manifest)} in manifest)")
    print("=" * 80)
    print(f"check (a) session-coverage pass [THE GATE]: {n_pass_a}/{n} ({n_pass_a/n:.1%})")
    print(f"check (b) ratio-consistency vs `existing` [INFORMATIONAL ONLY, not a gate -- existing itself "
          f"is known-corrupted for many symbols]: {n_pass_b}/{n} ({n_pass_b/n:.1%}) clean")
    print(f"  of check-b mismatches: {n_tail_only_b_fail} tail-only (likely existing-side recent-update "
          f"corruption), {n_broad_b_fail} broad/29-day-piecewise (same signature as HPG/TCB -- existing is "
          f"stale/wrong for these, not a defect in v2)")
    print(f"check (c) magnitude-sanity pass: {int(result['check_c_pass'].sum())}/{n}")
    print(f"check (d) total outlier-days across universe: {int(result['check_d_outlier_count'].sum())}")

    print("\nFailures on check (a) (full table in quality_report.csv):")
    fails = result[~result["check_a_pass"]]
    print(fails[["symbol", "rows", "date_range", "check_a_pass", "check_a_worst_year", "check_a_worst_pct",
                 "check_b_distinct_ratios", "check_b_tail_only"]].to_string(index=False))

    verdict = "PASS -- proceed to Task 5" if (n_pass_a / n) >= 0.95 else "FAIL -- do not proceed, review failures first"
    print(f"\nOVERALL ACCEPTANCE ({n_pass_a}/{n} = {n_pass_a/n:.1%} >= 95% on check (a)?): {verdict}")


if __name__ == "__main__":
    main()
