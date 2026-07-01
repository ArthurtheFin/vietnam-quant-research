from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.utils.pipeline_io import (
    DEFAULT_DATE_COLUMNS,
    dataframe_metadata,
    latest_timestamp,
    read_first_existing_parquet,
)


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    paths: tuple[str, ...]
    severity: str = "warning"
    required: bool = False
    date_columns: tuple[str, ...] = DEFAULT_DATE_COLUMNS


ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("clean_daily_ohlcv", ("data/processed/clean_daily_ohlcv.parquet",), severity="error", required=True),
    ArtifactSpec("stock_features", ("data/processed/stock_features.parquet",), severity="error", required=True),
    ArtifactSpec(
        "setup_signals",
        ("data/signals/setup_signals.parquet", "data/processed/setup_signals.parquet"),
        severity="error",
    ),
    ArtifactSpec("alpha_scores", ("data/signals/alpha_scores.parquet",), severity="warning"),
    ArtifactSpec("benchmark_vnindex", ("data/processed/benchmark_vnindex.parquet",), severity="warning"),
    ArtifactSpec("breakout_trade_cards", ("data/signals/breakout_20d_trade_cards.parquet",), severity="warning"),
    ArtifactSpec("stealth_latest", ("data/signals/stealth_accumulation_latest.parquet",), severity="warning"),
    ArtifactSpec(
        "meta_ranking",
        ("data/signals/meta_ranking.parquet", "data/processed/meta_ranking.parquet"),
        severity="error",
    ),
    ArtifactSpec("final_watchlist", ("data/signals/final_watchlist.parquet",), severity="warning"),
    ArtifactSpec("research_candidates", ("data/output/research_candidates.parquet",), severity="warning"),
    ArtifactSpec("trading_watchlist", ("data/output/trading_watchlist.parquet",), severity="warning"),
    ArtifactSpec("client_ready_watchlist", ("data/output/client_ready_watchlist.parquet",), severity="warning"),
)


DEPENDENCY_RULES: tuple[tuple[str, str, str], ...] = (
    ("clean_daily_ohlcv", "stock_features", "error"),
    ("stock_features", "setup_signals", "error"),
    ("stock_features", "alpha_scores", "warning"),
    ("stock_features", "benchmark_vnindex", "warning"),
    ("setup_signals", "breakout_trade_cards", "warning"),
    ("stock_features", "stealth_latest", "warning"),
    ("stock_features", "meta_ranking", "error"),
    ("meta_ranking", "final_watchlist", "warning"),
    ("meta_ranking", "trading_watchlist", "warning"),
    ("meta_ranking", "client_ready_watchlist", "warning"),
)


def inspect_artifacts(base_dir: str | Path = ".") -> dict[str, dict[str, object]]:
    base = Path(base_dir)
    inspected: dict[str, dict[str, object]] = {}

    for spec in ARTIFACT_SPECS:
        frame, resolved_path = read_first_existing_parquet(spec.paths, base_dir=base)
        latest = latest_timestamp(frame, candidates=spec.date_columns)
        inspected[spec.name] = {
            "name": spec.name,
            "required": spec.required,
            "severity": spec.severity,
            "exists": resolved_path is not None,
            "resolved_path": None if resolved_path is None else str(resolved_path),
            "latest_timestamp": latest,
            "metadata": dataframe_metadata(frame, path=resolved_path, date_candidates=spec.date_columns),
        }
    return inspected


def evaluate_freshness(
    base_dir: str | Path = ".",
    strict: bool = False,
) -> dict[str, object]:
    inspected = inspect_artifacts(base_dir=base_dir)
    warnings: list[str] = []
    errors: list[str] = []

    baseline_ts = (
        inspected.get("clean_daily_ohlcv", {}).get("latest_timestamp")
        or inspected.get("stock_features", {}).get("latest_timestamp")
    )
    baseline_date = None if baseline_ts is None else pd.Timestamp(baseline_ts)

    if baseline_date is None:
        errors.append("No baseline artifact found. Missing clean_daily_ohlcv / stock_features.")

    for spec in ARTIFACT_SPECS:
        item = inspected[spec.name]
        if not item["exists"]:
            message = f"Missing artifact: {spec.name}"
            if spec.required or spec.severity == "error":
                errors.append(message)
            else:
                warnings.append(message)
            continue

        latest = item["latest_timestamp"]
        if latest is None:
            message = f"Artifact has no usable date column: {spec.name}"
            if spec.severity == "error":
                errors.append(message)
            else:
                warnings.append(message)
            continue

        if baseline_date is not None:
            lag_days = int((baseline_date.normalize() - pd.Timestamp(latest).normalize()).days)
            item["lag_days_vs_baseline"] = lag_days
            if lag_days > 0:
                message = (
                    f"{spec.name} is stale by {lag_days} day(s). "
                    f"Latest {spec.name}: {pd.Timestamp(latest).date().isoformat()}, "
                    f"baseline: {baseline_date.date().isoformat()}."
                )
                if spec.severity == "error" or strict:
                    errors.append(message)
                else:
                    warnings.append(message)
        else:
            item["lag_days_vs_baseline"] = None

    for parent_name, child_name, severity in DEPENDENCY_RULES:
        parent = inspected.get(parent_name)
        child = inspected.get(child_name)
        if not parent or not child or not parent["exists"] or not child["exists"]:
            continue
        parent_ts = parent.get("latest_timestamp")
        child_ts = child.get("latest_timestamp")
        if parent_ts is None or child_ts is None:
            continue
        if pd.Timestamp(child_ts) < pd.Timestamp(parent_ts):
            message = (
                f"{child_name} was generated from stale inputs relative to {parent_name}. "
                f"{child_name} latest = {pd.Timestamp(child_ts).date().isoformat()}, "
                f"{parent_name} latest = {pd.Timestamp(parent_ts).date().isoformat()}."
            )
            if severity == "error" or strict:
                errors.append(message)
            else:
                warnings.append(message)

    status = "OK"
    if errors:
        status = "ERROR"
    elif warnings:
        status = "WARNING"

    artifact_summary = {
        name: {
            **{
                key: value
                for key, value in item.items()
                if key not in {"latest_timestamp"}
            },
            "latest_date": None
            if item.get("latest_timestamp") is None
            else pd.Timestamp(item["latest_timestamp"]).date().isoformat(),
        }
        for name, item in inspected.items()
    }

    return {
        "status": status,
        "baseline_date": None if baseline_date is None else baseline_date.date().isoformat(),
        "warnings": warnings,
        "errors": errors,
        "artifacts": artifact_summary,
    }


def _format_report(report: dict[str, object]) -> str:
    lines = [f"{report['status']}: freshness check"]
    baseline = report.get("baseline_date")
    if baseline:
        lines.append(f"Baseline date: {baseline}")
    for name, artifact in report.get("artifacts", {}).items():
        status = "FOUND" if artifact.get("exists") else "MISSING"
        lines.append(
            f"- {name}: {status}, latest_date={artifact.get('latest_date')}, "
            f"rows={artifact.get('metadata', {}).get('rows', 0)}, "
            f"symbols={artifact.get('metadata', {}).get('symbol_count', 0)}, "
            f"path={artifact.get('resolved_path')}"
        )
    for warning in report.get("warnings", []):
        lines.append(f"WARNING: {warning}")
    for error in report.get("errors", []):
        lines.append(f"ERROR: {error}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate freshness/alignment of pipeline artifacts.")
    parser.add_argument("--base-dir", default=".", help="Project root containing data/ and src/.")
    parser.add_argument("--strict", action="store_true", help="Treat stale warning-level artifacts as errors.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = evaluate_freshness(base_dir=args.base_dir, strict=args.strict)
    print(_format_report(report))
    return 1 if report["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
