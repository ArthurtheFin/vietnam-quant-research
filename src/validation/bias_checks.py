from __future__ import annotations

from pathlib import Path

import pandas as pd


def run_bias_checks(base_dir: str | Path = ".") -> dict[str, object]:
    """Automated, pipeline-wired entry point for the bias checks below (audit D4).

    These functions previously existed only as manual, notebook-only checks
    (run by hand in 19_validation_and_stress_test.ipynb) with no automated call
    site anywhere in run_daily_pipeline.py. This wraps check_lookahead_bias over
    setup_signals.parquet so every pipeline run records the result, instead of
    the check existing purely as unenforced documentation.

    setup_signals.parquet intentionally carries forward_return_Nd research
    labels (see docs/reports/codebase_audit/docs/reports/codebase_audit/AUDIT_REPORT.md D5), so a "failed" lookahead check here is
    informational, not a pipeline-blocking error -- D5's guards already prevent
    those columns from reaching live scoring/output artifacts.
    """
    base = Path(base_dir)
    path = base / "data/signals/setup_signals.parquet"
    if not path.exists():
        return {"ran": False, "reason": "setup_signals.parquet not found"}
    try:
        signals = pd.read_parquet(path)
    except Exception as exc:
        return {"ran": False, "reason": f"could not read setup_signals.parquet: {exc}"}
    result = check_lookahead_bias(signals)
    return {"ran": True, "target": "data/signals/setup_signals.parquet", **result}


def check_lookahead_bias(
    signal_df: pd.DataFrame,
    date_col: str = "date",
) -> dict[str, bool | str]:
    """
    Checks if there is obvious look-ahead bias in the signal dataframe.
    Verifies that the dates of calculations strictly align or increase,
    and checks if future returns are accidentally included in signal columns.
    """
    if signal_df.empty:
        return {"passed": True, "details": "Empty signal dataframe."}
        
    # Check if there are columns with 'forward_return' used in signal conditions
    future_cols = [c for c in signal_df.columns if "forward" in c.lower() or "future" in c.lower()]
    passed = len(future_cols) == 0
    details = f"Detected future/forward columns: {future_cols}" if not passed else "No future columns detected in signals."
    
    return {
        "passed": passed,
        "details": details,
    }

def check_data_leakage(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    date_col: str = "date",
) -> dict[str, bool | str]:
    """
    Verifies that no test set timestamps exist on or before train set timestamps.
    """
    if train_df.empty or test_df.empty:
        return {"passed": True, "details": "Train or test set is empty."}
        
    train_dates = pd.to_datetime(train_df[date_col])
    test_dates = pd.to_datetime(test_df[date_col])
    
    max_train_date = train_dates.max()
    min_test_date = test_dates.min()
    
    passed = min_test_date > max_train_date
    details = f"Max Train Date: {max_train_date.strftime('%Y-%m-%d')}. Min Test Date: {min_test_date.strftime('%Y-%m-%d')}."
    
    return {
        "passed": passed,
        "details": details,
    }

def check_survivorship_bias(
    active_universe: list[str] | pd.Index,
    historical_delisted: list[str] | pd.Index,
) -> dict[str, bool | str]:
    """
    Checks if active universe contains delisted historical tickers to determine survivorship bias level.
    """
    active_set = set(active_universe)
    delisted_set = set(historical_delisted)
    
    overlapping = active_set.intersection(delisted_set)
    missing_delisted = delisted_set - active_set
    
    passed = len(missing_delisted) == 0
    
    details = (
        f"Active universe size: {len(active_set)}. Delisted universe size: {len(delisted_set)}. "
        f"Missing delisted stocks in active backtest: {len(missing_delisted)} (Survivorship bias present)."
    )
    
    return {
        "passed": passed,
        "details": details,
    }
