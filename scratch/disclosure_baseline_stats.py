"""One-off descriptive-stats generator for docs/reports/data/docs/reports/data/DISCLOSURE_BASELINE.md.

Descriptive only -- deliberately computes nothing involving price or return
data (no join against data/full_history_v2 or any other price source). See
docs/reports/data/docs/reports/data/DISCLOSURE_PIPELINE_DESIGN.md Round 5 for why that boundary matters here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVENTS_PATH = PROJECT_ROOT / "data/disclosure/events.parquet"
ERRORS_PATH = PROJECT_ROOT / "data/disclosure/errors.parquet"
RAW_DIR = PROJECT_ROOT / "data/disclosure/raw"


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = pd.read_parquet(EVENTS_PATH)
    errors = pd.read_parquet(ERRORS_PATH)
    common_cols = [c for c in events.columns if c in errors.columns]
    frames = [df[common_cols] for df in (events, errors) if not df.empty]
    allrows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=common_cols)
    return events, errors, allrows


def dataset_identity(events: pd.DataFrame, errors: pd.DataFrame) -> dict:
    manifest = json.loads((RAW_DIR / "manifest.json").read_text(encoding="utf-8"))
    n_symbols_ok = sum(1 for v in manifest.values() if v.get("status") == "ok")
    n_symbols_error = sum(1 for v in manifest.values() if v.get("status") == "error")
    raw_size_bytes = sum(f.stat().st_size for f in RAW_DIR.rglob("*.json"))
    events_size = EVENTS_PATH.stat().st_size if EVENTS_PATH.exists() else 0
    errors_size = ERRORS_PATH.stat().st_size if ERRORS_PATH.exists() else 0
    return {
        "n_symbols_crawled_ok": n_symbols_ok,
        "n_symbols_crawl_error": n_symbols_error,
        "n_valid_events": len(events),
        "n_rejected_rows": len(errors),
        "raw_tier_size_mb": round(raw_size_bytes / 1e6, 1),
        "events_parquet_size_mb": round(events_size / 1e6, 2),
        "errors_parquet_size_mb": round(errors_size / 1e6, 2),
    }


def registration_result_match_rate(allrows: pd.DataFrame) -> dict:
    insider_mask = allrows["event_type"].isin(["insider_registration", "insider_result"])
    insider = allrows.loc[insider_mask]
    by_link = insider.groupby("link_key")["event_type"].agg(lambda s: set(s))
    n_both = int((by_link.apply(lambda s: {"insider_registration", "insider_result"} <= s)).sum())
    n_reg_only = int((by_link.apply(lambda s: s == {"insider_registration"})).sum())
    n_result_only = int((by_link.apply(lambda s: s == {"insider_result"})).sum())
    total_links = len(by_link)
    return {
        "n_insider_link_keys": total_links,
        "n_matched_both_phases": n_both,
        "n_registration_only": n_reg_only,
        "n_result_only": n_result_only,
        "match_rate_pct": round(100 * n_both / total_links, 1) if total_links else 0.0,
    }


def year_event_direction_table(allrows: pd.DataFrame) -> pd.DataFrame:
    df = allrows.copy()
    df["year"] = pd.to_datetime(df["disclosure_date"]).dt.year
    table = df.groupby(["year", "event_type", "direction"], dropna=False).size().unstack(["event_type", "direction"], fill_value=0)
    return table


def historical_depth_histogram(allrows: pd.DataFrame) -> pd.Series:
    df = allrows.copy()
    df["year"] = pd.to_datetime(df["disclosure_date"]).dt.year
    earliest_year_per_symbol = df.groupby("symbol")["year"].min()
    bins = [0, 2009, 2013, 2017, 2021, 2025, 2100]
    labels = ["<=2008", "2009-2012", "2013-2016", "2017-2020", "2021-2024", "2025+"]
    bucketed = pd.cut(earliest_year_per_symbol, bins=bins, labels=labels, right=True)
    return bucketed.value_counts().reindex(labels)


def role_distribution(allrows: pd.DataFrame) -> pd.Series:
    df = allrows.copy()

    def categorize(row) -> str:
        if row["event_type"] == "major_shareholder_change":
            return "major_shareholder"
        if str(row.get("related_person_role") or "").strip():
            return "related_person"
        return "insider"

    return df.apply(categorize, axis=1).value_counts()


def execution_registration_ratio(allrows: pd.DataFrame) -> pd.Series:
    """Share-count ratio only (executed / registered volume) -- no price
    or return involved anywhere in this computation."""
    df = allrows[allrows["event_type"].isin(["insider_registration", "insider_result"])].copy()
    pivot = df.pivot_table(
        index="link_key", columns="event_type", values="shares_registered_or_changed", aggfunc="first"
    )
    pivot = pivot.dropna(subset=["insider_registration", "insider_result"])
    pivot = pivot[pivot["insider_registration"] > 0]
    ratio = (pivot["insider_result"] / pivot["insider_registration"]).clip(upper=2.0)  # cap display outliers
    return ratio.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])


def field_completeness_by_year(allrows: pd.DataFrame) -> pd.DataFrame:
    df = allrows.copy()
    df["year"] = pd.to_datetime(df["disclosure_date"]).dt.year
    required = ["symbol", "event_type", "person_name", "direction", "disclosure_date"]
    df["is_complete"] = df[required].notna().all(axis=1) & (df["person_name"].astype(str).str.len() > 0)
    return df.groupby("year")["is_complete"].agg(["mean", "count"]).rename(columns={"mean": "pct_complete", "count": "n_rows"})


def error_breakdown(errors: pd.DataFrame) -> pd.Series:
    return errors["reject_reason"].value_counts()


if __name__ == "__main__":
    events, errors, allrows = load()
    print("=== dataset identity ===")
    print(json.dumps(dataset_identity(events, errors), indent=2, ensure_ascii=False))
    print("\n=== registration/result match rate ===")
    print(json.dumps(registration_result_match_rate(allrows), indent=2, ensure_ascii=False))
    print("\n=== year x event_type x direction ===")
    print(year_event_direction_table(allrows))
    print("\n=== historical depth histogram (earliest disclosure year per symbol) ===")
    print(historical_depth_histogram(allrows))
    print("\n=== role distribution ===")
    print(role_distribution(allrows))
    print("\n=== execution/registration ratio distribution ===")
    print(execution_registration_ratio(allrows))
    print("\n=== field completeness by year ===")
    print(field_completeness_by_year(allrows).to_string())
    print("\n=== error breakdown ===")
    print(error_breakdown(errors))
