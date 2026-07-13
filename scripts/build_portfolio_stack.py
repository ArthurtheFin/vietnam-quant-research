from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.capital.management import align_capital_plan_to_target_weights, build_capital_plan
from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet
from src.portfolio.construction import (
    equal_weight_allocation,
    hierarchical_risk_parity_allocation,
    inverse_volatility_allocation,
    risk_parity_allocation,
)
from src.portfolio.input_resolver import load_default_portfolio_candidates
from src.risk.management import build_portfolio_risk_report
from src.utils.pipeline_io import (
    relative_path,
    utc_now_iso,
    validate_portfolio_stack_metadata,
    write_json,
)


OUTPUT_DIR = PROJECT_ROOT / "data/output"

DEFAULT_NAV = 1_000_000_000.0


def _resolve_nav(warnings: list[str]) -> float:
    """NAV for capital plan sizing, from config/strategy_config.yaml:portfolio.nav
    (audit H6) -- falls back to DEFAULT_NAV with an explicit warning, never silently."""
    import yaml

    config_path = PROJECT_ROOT / "config/strategy_config.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        nav = cfg.get("portfolio", {}).get("nav")
        if nav is not None:
            return float(nav)
    except Exception as exc:
        warnings.append(f"Could not read portfolio.nav from strategy_config.yaml ({exc}); using default NAV.")
        return DEFAULT_NAV
    warnings.append(
        f"portfolio.nav not set in strategy_config.yaml; using default NAV {DEFAULT_NAV:,.0f} VND."
    )
    return DEFAULT_NAV


def _normalize_metadata(metadata: dict[str, object]) -> dict[str, object]:
    out = dict(metadata)
    out["source_path"] = relative_path(out.get("source_path"), PROJECT_ROOT)
    out["features_path"] = relative_path(out.get("features_path"), PROJECT_ROOT)
    return out


def _add_source_metadata(df: pd.DataFrame, metadata: dict[str, object]) -> pd.DataFrame:
    out = df.copy()
    out["source_watchlist_file"] = metadata.get("source_path")
    out["source_latest_date"] = metadata.get("source_latest_date")
    out["generated_at"] = utc_now_iso()
    out["symbols_used"] = ",".join(metadata.get("used_symbols", metadata.get("symbols", [])))
    return out


def _resolve_inverse_vol_input(
    candidates: pd.DataFrame,
    return_matrix: pd.DataFrame,
    warnings: list[str],
) -> pd.Series:
    """Volatility input for inverse-vol weights. Never substitutes a score for vol (audit H1)."""
    if "atr_pct_14" in candidates.columns:
        return (
            candidates.set_index("symbol")
            .reindex(return_matrix.columns)["atr_pct_14"]
            .ffill()
            .bfill()
            .fillna(0.02)
        )
    warnings.append(
        "atr_pct_14 missing from candidates; using annualized realized vol "
        "from return matrix for inverse-volatility allocation"
    )
    realized = return_matrix.std(ddof=0) * np.sqrt(252.0)
    return realized.replace(0.0, np.nan).fillna(0.02)


def _build_allocations(
    return_matrix: pd.DataFrame,
    latest_vol: pd.Series,
    covariance: pd.DataFrame,
    warnings: list[str],
) -> tuple[dict[str, pd.Series], set[str]]:
    """Run each allocator; on failure substitute equal weight but record it loudly (audit H2)."""
    fallback_used: set[str] = set()
    allocations: dict[str, pd.Series] = {}
    builders = {
        "equal_weight": lambda: equal_weight_allocation(return_matrix.columns),
        "inverse_volatility": lambda: inverse_volatility_allocation(latest_vol.abs().replace(0, 0.02)),
        "risk_parity": lambda: risk_parity_allocation(covariance),
        "hrp": lambda: hierarchical_risk_parity_allocation(returns=return_matrix),
    }
    for name, builder in builders.items():
        try:
            allocations[name] = builder()
        except Exception as exc:
            fallback_used.add(name)
            warnings.append(f"{name} allocation failed ({exc}); equal-weight substituted")
            allocations[name] = equal_weight_allocation(return_matrix.columns)
    return allocations, fallback_used


def _build_return_matrix(features: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    work = features[features["symbol"].astype(str).str.upper().isin(symbols)].copy()
    if work.empty:
        return pd.DataFrame()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    if "return_1d" not in work.columns and "close" in work.columns:
        work = work.sort_values(["symbol", "date"]).copy()
        work["return_1d"] = work.groupby("symbol")["close"].pct_change(1)
    return (
        work.pivot_table(index="date", columns="symbol", values="return_1d", aggfunc="last")
        .sort_index()
        .dropna(axis=1, how="all")
    )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates, source_metadata = load_default_portfolio_candidates(PROJECT_ROOT)
    source_metadata = _normalize_metadata(source_metadata)
    warnings: list[str] = []
    rejected_reasons = source_metadata.get("rejected_symbols_portfolio_gate", {})
    if rejected_reasons:
        for sym, reason in rejected_reasons.items():
            warnings.append(f"Rejected symbol {sym} from portfolio construction due to eligibility: {reason}")

    if candidates.empty:
        warnings.append("No portfolio candidates available after eligibility gate filtering.")
        
        empty_weights = pd.DataFrame(columns=["symbol", "equal_weight", "inverse_volatility", "risk_parity", "hrp"])
        portfolio_weights_path = OUTPUT_DIR / "portfolio_weights.parquet"
        save_parquet(empty_weights, portfolio_weights_path)
        
        empty_risk = {
            "portfolio_volatility": 0.0,
            "portfolio_variance": 0.0,
            "diversification_ratio": 1.0,
            "marginal_contributions": {},
            "component_risk_contributions": {},
            "relative_marginal_risk_contributions": {},
            "portfolio_return": 0.0,
            "sharpe_ratio": 0.0,
            "tracking_error": 0.0,
            "information_ratio": 0.0,
            "beta": 0.0,
            "active_share": 1.0,
            "alpha": 0.0,
            "r_squared": 0.0,
            "warnings": warnings,
            "generated_at": utc_now_iso(),
            "used_symbols": [],
            "missing_symbols": source_metadata.get("missing_symbols", []),
            "rejected_symbols_portfolio_gate": rejected_reasons,
        }
        empty_risk.update(source_metadata)
        portfolio_risk_report_path = OUTPUT_DIR / "portfolio_risk_report.json"
        write_json(empty_risk, portfolio_risk_report_path)
        
        portfolio_candidates_path = OUTPUT_DIR / "portfolio_candidates.parquet"
        save_parquet(pd.DataFrame(), portfolio_candidates_path)
        
        capital_plan_path = OUTPUT_DIR / "capital_plan.parquet"
        save_parquet(pd.DataFrame(), capital_plan_path)
        
        generated_files = [
            relative_path(portfolio_candidates_path, PROJECT_ROOT),
            relative_path(portfolio_weights_path, PROJECT_ROOT),
            relative_path(portfolio_risk_report_path, PROJECT_ROOT),
            relative_path(capital_plan_path, PROJECT_ROOT),
        ]
        
        stack_metadata = {
            **source_metadata,
            "status": "WARNING",
            "warnings": warnings,
            "generated_at": utc_now_iso(),
            "source_watchlist": source_metadata.get("source_name"),
            "source_file": source_metadata.get("source_path"),
            "symbols_used": [],
            "portfolio_symbols": [],
            "missing_symbols": source_metadata.get("missing_symbols", []),
            "candidate_rows": 0,
            "return_matrix_rows": 0,
            "return_matrix_symbols": 0,
            "generated_files": generated_files,
            "outputs": {
                "portfolio_candidates": generated_files[0],
                "portfolio_weights": generated_files[1],
                "portfolio_risk_report": generated_files[2],
                "capital_plan": generated_files[3],
            },
        }
        validate_portfolio_stack_metadata(stack_metadata)
        write_json(stack_metadata, OUTPUT_DIR / "portfolio_stack_metadata.json")
        
        print("=== Portfolio Stack Complete with WARNING (Empty candidates) ===")
        return 0

    features = read_parquet(PROJECT_ROOT / OFFICIAL_FEATURES_PATH)
    benchmark = read_parquet(PROJECT_ROOT / "data/processed/benchmark_vnindex.parquet")
    symbols = candidates["symbol"].dropna().astype(str).str.upper().tolist()
    return_matrix = _build_return_matrix(features, symbols)
    if return_matrix.empty:
        raise SystemExit("No return matrix available for selected portfolio symbols.")

    warnings: list[str] = []
    if source_metadata.get("missing_symbols"):
        warnings.append(
            "Missing symbols in stock_features: "
            + ", ".join(source_metadata.get("missing_symbols", []))
        )

    latest_vol = _resolve_inverse_vol_input(candidates, return_matrix, warnings)
    covariance = return_matrix.cov().fillna(0.0)

    allocations, fallback_used = _build_allocations(return_matrix, latest_vol, covariance, warnings)

    weights_table = pd.concat([series.rename(name) for name, series in allocations.items()], axis=1).fillna(0.0)
    weights_table = weights_table.reset_index().rename(columns={"index": "symbol"})
    weights_table["allocation_fallbacks"] = ",".join(sorted(fallback_used))
    weights_table = _add_source_metadata(weights_table, source_metadata)
    portfolio_weights_path = OUTPUT_DIR / "portfolio_weights.parquet"
    save_parquet(weights_table, portfolio_weights_path)

    default_weights = allocations.get("risk_parity")
    if default_weights is None or default_weights.empty:
        default_weights = allocations["equal_weight"]

    benchmark_returns = pd.Series(dtype=float)
    if not benchmark.empty:
        benchmark = benchmark.copy()
        benchmark["date"] = pd.to_datetime(benchmark["date"], errors="coerce")
        if "return_1d" not in benchmark.columns and "close" in benchmark.columns:
            benchmark["return_1d"] = benchmark["close"].pct_change(1)
        benchmark_returns = benchmark.set_index("date")["return_1d"].astype(float)

    risk_report = build_portfolio_risk_report(
        return_matrix=return_matrix,
        weights=default_weights,
        benchmark_returns=benchmark_returns if not benchmark_returns.empty else None,
    )
    risk_report.update(source_metadata)
    risk_report["generated_at"] = utc_now_iso()
    risk_report["allocator_used"] = (
        "equal_weight (risk_parity FAILED)" if "risk_parity" in fallback_used else "risk_parity"
    )
    risk_report["allocation_fallbacks"] = sorted(fallback_used)
    risk_report["warnings"] = warnings
    portfolio_risk_report_path = OUTPUT_DIR / "portfolio_risk_report.json"
    write_json(risk_report, portfolio_risk_report_path)

    candidates_with_meta = _add_source_metadata(candidates, source_metadata)
    portfolio_candidates_path = OUTPUT_DIR / "portfolio_candidates.parquet"
    save_parquet(candidates_with_meta, portfolio_candidates_path)

    nav = _resolve_nav(warnings)
    capital_plan = build_capital_plan(
        candidates=candidates,
        nav=nav,
        p_win_col="win_rate" if "win_rate" in candidates.columns else None,
        avg_gain_col="avg_return" if "avg_return" in candidates.columns else None,
        # Kelly requires a true loss statistic; median_return is not one (audit H3).
        avg_loss_col="avg_loss" if "avg_loss" in candidates.columns else None,
        max_gross_exposure=0.95,
    )
    if not capital_plan.empty:
        aligned_plan = align_capital_plan_to_target_weights(
            plan=capital_plan,
            target_weights=default_weights,
            nav=nav,
            max_gross_exposure=0.95,
        )
    else:
        aligned_plan = pd.DataFrame()
    aligned_plan = _add_source_metadata(aligned_plan, source_metadata) if not aligned_plan.empty else aligned_plan
    capital_plan_path = OUTPUT_DIR / "capital_plan.parquet"
    save_parquet(aligned_plan, capital_plan_path)

    generated_files = [
        relative_path(portfolio_candidates_path, PROJECT_ROOT),
        relative_path(portfolio_weights_path, PROJECT_ROOT),
        relative_path(portfolio_risk_report_path, PROJECT_ROOT),
        relative_path(capital_plan_path, PROJECT_ROOT),
    ]

    stack_metadata = {
        **source_metadata,
        "status": "WARNING" if warnings else "OK",
        "warnings": warnings,
        "generated_at": utc_now_iso(),
        "source_watchlist": source_metadata.get("source_name"),
        "source_file": source_metadata.get("source_path"),
        "symbols_used": symbols,
        "portfolio_symbols": symbols,
        "missing_symbols": source_metadata.get("missing_symbols", []),
        "candidate_rows": int(len(candidates)),
        "return_matrix_rows": int(len(return_matrix)),
        "return_matrix_symbols": int(len(return_matrix.columns)),
        "generated_files": generated_files,
        "outputs": {
            "portfolio_candidates": generated_files[0],
            "portfolio_weights": generated_files[1],
            "portfolio_risk_report": generated_files[2],
            "capital_plan": generated_files[3],
        },
    }
    validate_portfolio_stack_metadata(stack_metadata)
    write_json(stack_metadata, OUTPUT_DIR / "portfolio_stack_metadata.json")

    print("=== Portfolio Stack Complete ===")
    print("Source watchlist:", source_metadata.get("source_name"))
    print("Source file:", source_metadata.get("source_path"))
    print("Source latest date:", source_metadata.get("source_latest_date"))
    print("Symbols used:", len(symbols))
    print("Missing symbols:", len(source_metadata.get("missing_symbols", [])))
    print("Generated files:", ", ".join(generated_files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
