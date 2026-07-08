from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.data.loaders import read_parquet
from src.utils.logger import get_logger
from src.utils.pipeline_io import (
    dataframe_metadata,
    relative_path,
    resolve_watchlist_source,
    utc_now_iso,
    validate_pipeline_metadata,
    write_run_snapshot,
    write_json,
)
from src.validation.freshness_check import evaluate_freshness

LOGGER = get_logger("daily_pipeline")


PIPELINE_STEPS = [
    {
        "name": "generate_features",
        "script": "scripts/generate_features.py",
        "outputs": ["data/processed/stock_features.parquet", "data/processed/benchmark_vnindex.parquet"],
    },
    {
        "name": "generate_signals",
        "script": "scripts/generate_signals.py",
        "outputs": ["data/signals/setup_signals.parquet"],
    },
    {
        "name": "run_alpha_scoring",
        "script": "scripts/run_alpha_scoring.py",
        "outputs": ["data/signals/alpha_scores.parquet"],
    },
    {
        "name": "generate_trade_cards",
        "script": "scripts/generate_trade_cards.py",
        "outputs": ["data/signals/breakout_20d_trade_cards.parquet"],
    },
    {
        "name": "run_stealth_accumulation_screen",
        "script": "scripts/run_stealth_accumulation_screen.py",
        "outputs": [
            "data/signals/stealth_accumulation_history.parquet",
            "data/signals/stealth_accumulation_latest.parquet",
        ],
    },
    {
        # Symbol-level cashflow board MUST precede meta ranking so the
        # eligibility gate reads a same-day artifact (audit F1).
        "name": "build_cashflow_board_symbols",
        "script": "scripts/build_cashflow_board.py",
        "args": ["--symbol-only"],
        "outputs": ["data/output/cashflow_board.parquet"],
    },
    {
        "name": "run_meta_ranking",
        "script": "scripts/run_meta_ranking.py",
        "outputs": [
            "data/signals/meta_ranking.parquet",
            "data/signals/final_watchlist.parquet",
            "data/output/research_candidates.parquet",
            "data/output/trading_watchlist.parquet",
            "data/output/client_ready_watchlist.parquet",
        ],
    },
]

ONLINE_DAILY_STEPS = [
    {
        "name": "update_daily_data",
        "script": "scripts/update_daily_data.py",
        "outputs": ["data/raw"],
    },
]

ONLINE_INDEX_STEPS = [
    {
        "name": "update_index_data",
        "script": "scripts/update_index_data.py",
        "outputs": [
            "data/raw/index_ohlcv",
            "data/processed/index_features.parquet",
            "data/processed/benchmark_vnindex.parquet",
        ],
    },
]

ONLINE_STEP_NAMES = {"update_daily_data", "update_index_data"}
TOLERABLE_ONLINE_ERROR_CATEGORIES = {"PROVIDER_RATE_LIMIT", "PROVIDER_EMPTY_RESPONSE"}


def _sanitize_error_message(raw_error: str | None) -> str | None:
    if not raw_error:
        return None
    text = raw_error.replace(str(PROJECT_ROOT), ".").replace(str(Path.home()), "~")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    message = re.sub(r"\s+", " ", lines[-1])
    if len(message) > 280:
        message = message[:277] + "..."
    return message


def _classify_error(raw_error: str | None) -> str:
    normalized = (raw_error or "").lower()
    if "missing fcdata credential" in normalized or "create `.env`" in normalized:
        return "MISSING_ENV"
    if (
        "429" in normalized
        or "quota" in normalized
        or "rate limit" in normalized
        or "too many requests" in normalized
        or "exceeded" in normalized
    ):
        return "PROVIDER_RATE_LIMIT"
    if (
        "expecting value" in normalized
        or "empty response" in normalized
        or "khong co raw index data sau khi fetch" in normalized
        or "no raw index data after fetch" in normalized
    ):
        return "PROVIDER_EMPTY_RESPONSE"
    if (
        "schema" in normalized
        or "missing required key" in normalized
        or "missing column" in normalized
        or "keyerror" in normalized
    ):
        return "DATA_SCHEMA_ERROR"
    if "traceback" in normalized:
        return "CODE_ERROR"
    return "UNKNOWN_ERROR"


def _recommended_action(error_category: str, mode: str, step_name: str) -> str | None:
    if error_category == "PROVIDER_RATE_LIMIT_PARTIAL":
        return "Rerun online update later or use offline mode if cached data is already fresh enough."
    if error_category == "PROVIDER_RATE_LIMIT":
        return "Wait and rerun online update later, or use offline mode if data is already fresh."
    if error_category == "PROVIDER_EMPTY_RESPONSE":
        return "Rerun online update later and verify the SSI provider is returning data before rebuilding benchmarks."
    if error_category == "MISSING_ENV":
        return "Populate SSI credentials in `.env` from `.env.example`, then rerun online mode."
    if error_category == "DATA_SCHEMA_ERROR":
        return f"Inspect `{step_name}` inputs/outputs for schema drift before rerunning `{mode}` mode."
    if error_category == "CODE_ERROR":
        return f"Inspect `{step_name}` stack trace and fix the code path before rerunning `{mode}` mode."
    return "Inspect logs and rerun the pipeline after confirming provider/data availability."


def _build_online_update_metadata(enabled: bool) -> dict[str, object]:
    return {
        "enabled": enabled,
        "status": "SKIPPED" if not enabled else "OK",
        "error_category": None,
        "error_message": None,
        "recommended_action": None,
        "warnings": [],
        "steps": [],
        "failed_symbols": [],
    }


def _build_sector_board_metadata(
    enabled: bool = False,
    status: str | None = None,
    latest_date: str | None = None,
    n_sectors: int | None = None,
    generated_files: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"enabled": enabled}
    if enabled:
        payload.update(
            {
                "status": status or "ERROR",
                "latest_date": latest_date,
                "n_sectors": n_sectors or 0,
                "generated_files": generated_files or [],
                "warnings": warnings or [],
            }
        )
    return payload


def _default_sector_board_metadata() -> dict[str, object]:
    return _build_sector_board_metadata(enabled=False)


def _build_cashflow_board_metadata(
    enabled: bool = False,
    status: str | None = None,
    latest_date: str | None = None,
    n_symbols: int | None = None,
    n_sectors: int | None = None,
    value_proxy_used: bool | None = None,
    n_data_quality_warnings: int | None = None,
    n_low_liquidity_symbols: int | None = None,
    n_zero_volume_symbols: int | None = None,
    confirmation_counts: dict[str, int] | None = None,
    sector_score_warnings: list[str] | None = None,
    generated_files: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"enabled": enabled}
    if enabled:
        payload.update(
            {
                "status": status or "ERROR",
                "latest_date": latest_date,
                "n_symbols": n_symbols or 0,
                "n_sectors": n_sectors or 0,
                "value_proxy_used": value_proxy_used or False,
                "n_data_quality_warnings": n_data_quality_warnings or 0,
                "n_low_liquidity_symbols": n_low_liquidity_symbols or 0,
                "n_zero_volume_symbols": n_zero_volume_symbols or 0,
                "confirmation_counts": confirmation_counts or {},
                "sector_score_warnings": sector_score_warnings or [],
                "generated_files": generated_files or [],
                "warnings": warnings or [],
            }
        )
    return payload


def _default_cashflow_board_metadata() -> dict[str, object]:
    return _build_cashflow_board_metadata(enabled=False)


def _read_artifact_summary(path: str | Path) -> dict[str, object]:
    artifact_path = PROJECT_ROOT / path
    suffix = artifact_path.suffix.lower()
    if artifact_path.is_dir():
        return {
            "path": relative_path(artifact_path, PROJECT_ROOT),
            "exists": artifact_path.exists(),
            "rows": None,
            "columns": None,
            "symbol_count": None,
            "latest_date": None,
        }
    if suffix == ".json":
        payload: dict[str, object] = {}
        if artifact_path.exists():
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        return {
            "path": relative_path(artifact_path, PROJECT_ROOT),
            "exists": artifact_path.exists(),
            "rows": None,
            "columns": None,
            "symbol_count": payload.get("symbol_count"),
            "latest_date": payload.get("source_latest_date") or payload.get("latest_date"),
        }
    if not artifact_path.exists():
        return {
            "path": relative_path(artifact_path, PROJECT_ROOT),
            "exists": False,
            "rows": None,
            "columns": None,
            "symbol_count": None,
            "latest_date": None,
        }
    if suffix == ".parquet":
        df = read_parquet(artifact_path)
    elif suffix == ".csv":
        df = pd.read_csv(artifact_path)
    else:
        return {
            "path": relative_path(artifact_path, PROJECT_ROOT),
            "exists": True,
            "rows": None,
            "columns": None,
            "symbol_count": None,
            "latest_date": None,
        }
    summary = dataframe_metadata(df, path=artifact_path)
    summary["path"] = relative_path(artifact_path, PROJECT_ROOT)
    summary["exists"] = artifact_path.exists()
    return summary


def _ensure_online_ready() -> None:
    from src.data import fcdata_config

    try:
        fcdata_config.validate_config()
    except EnvironmentError as exc:
        raise SystemExit(str(exc)) from exc


def _run_step(step: dict[str, object], args_context: argparse.Namespace = None) -> dict[str, object]:
    script = str(step["script"])
    cmd = [sys.executable, script, *[str(arg) for arg in step.get("args", [])]]
    if step["name"] == "update_daily_data" and args_context:
        update_scope = getattr(args_context, "update_scope", None)
        if update_scope:
            cmd.extend(["--scope", update_scope])
        batch_id = getattr(args_context, "batch_id", None)
        if batch_id is not None:
            cmd.extend(["--batch-id", str(batch_id)])
        batch_count = getattr(args_context, "batch_count", None)
        if batch_count is not None:
            cmd.extend(["--batch-count", str(batch_count)])
        update_symbols = getattr(args_context, "update_symbols", None)
        if update_symbols:
            cmd.extend(["--symbols", update_symbols])
        workers = getattr(args_context, "workers", None)
        if workers is not None:
            cmd.extend(["--workers", str(workers)])
    LOGGER.info("Running step `%s` via `%s`", step["name"], " ".join(cmd))
    started = time.time()
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    duration = round(time.time() - started, 2)

    if result.stdout.strip():
        LOGGER.info("Step `%s` stdout:\n%s", step["name"], result.stdout.strip())
    if result.stderr.strip():
        LOGGER.warning("Step `%s` stderr:\n%s", step["name"], result.stderr.strip())

    summaries = [_read_artifact_summary(path) for path in step.get("outputs", [])]
    raw_error = (result.stderr or result.stdout).strip() if result.returncode != 0 else None
    error_category = _classify_error(raw_error) if raw_error else None
    error_message = _sanitize_error_message(raw_error)
    status = "OK" if result.returncode == 0 else "ERROR"
    stdout_lower = (result.stdout or "").lower()
    if step["name"] in ONLINE_STEP_NAMES and result.returncode == 0 and "[failed]" in stdout_lower:
        status = "WARNING"
        error_category = "PROVIDER_RATE_LIMIT_PARTIAL" if any(
            token in stdout_lower for token in ["429", "quota", "rate limit", "exceeded"]
        ) else "UNKNOWN_ERROR"
        error_message = "Online update completed with partial fetch failures; some symbols may have reused cached history."
    payload = {
        "name": step["name"],
        "script": script,
        "duration_seconds": duration,
        "return_code": int(result.returncode),
        "status": status,
        "outputs": summaries,
        "error_category": error_category,
        "error_message": error_message,
        "recommended_action": _recommended_action(error_category, "pipeline", str(step["name"])) if error_category else None,
    }
    return payload


def _benchmark_status(freshness: dict[str, object]) -> dict[str, object]:
    artifacts = freshness.get("artifacts", {})
    benchmark = artifacts.get("benchmark_vnindex", {})
    stock = artifacts.get("stock_features", {})
    benchmark_latest = benchmark.get("latest_date")
    stock_latest = stock.get("latest_date")
    if benchmark_latest and stock_latest and benchmark_latest < stock_latest:
        return {
            "status": "WARNING",
            "benchmark_latest_date": benchmark_latest,
            "stock_latest_date": stock_latest,
            "reason": "Offline pipeline rebuilds benchmark from local raw index parquet, and local VNINDEX raw data only reaches the older date.",
            "recommended_action": "Run `python scripts/update_index_data.py` in online mode after SSI index data is available to refresh VNINDEX raw history.",
        }
    return {
        "status": "OK",
        "benchmark_latest_date": benchmark_latest,
        "stock_latest_date": stock_latest,
        "reason": None,
        "recommended_action": None,
    }


def _build_portfolio_stack_metadata(
    enabled: bool = False,
    status: str | None = None,
    warnings: list[str] | None = None,
    generated_files: list[str] | None = None,
    source_watchlist: str | None = None,
    symbols_used: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": enabled,
    }
    if enabled:
        payload.update(
            {
                "status": status or "ERROR",
                "warnings": warnings or [],
                "generated_files": generated_files or [],
                "source_watchlist": source_watchlist,
                "symbols_used": symbols_used or [],
            }
        )
        payload.update(extra)
    return payload


def _default_portfolio_stack_metadata() -> dict[str, object]:
    return _build_portfolio_stack_metadata(enabled=False)


def _resolve_steps_to_run(mode: str, update_index: bool) -> list[dict[str, object]]:
    steps_to_run = list(PIPELINE_STEPS)
    if mode != "online":
        return steps_to_run
    online_prefix_steps = list(ONLINE_DAILY_STEPS)
    if update_index:
        online_prefix_steps = ONLINE_INDEX_STEPS + online_prefix_steps
    return online_prefix_steps + steps_to_run


def _run_portfolio_stack() -> dict[str, object]:
    step = {
        "name": "build_portfolio_stack",
        "script": "scripts/build_portfolio_stack.py",
        "outputs": [
            "data/output/portfolio_candidates.parquet",
            "data/output/portfolio_weights.parquet",
            "data/output/capital_plan.parquet",
            "data/output/portfolio_stack_metadata.json",
            "data/output/portfolio_risk_report.json",
        ],
    }
    report = _run_step(step)
    metadata_path = PROJECT_ROOT / "data/output/portfolio_stack_metadata.json"
    stack_payload = {
        "enabled": True,
        "status": report["status"],
        "warnings": [],
        "generated_files": [],
        "source_watchlist": None,
        "symbols_used": [],
    }
    if metadata_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        stack_payload.update(
            {
                "status": payload.get("status", report["status"]),
                "warnings": payload.get("warnings", []),
                "generated_files": payload.get("generated_files", []),
                "source_watchlist": payload.get("source_path"),
                "symbols_used": payload.get("used_symbols", payload.get("symbols", [])),
                "source_watchlist_name": payload.get("source_name"),
                "source_latest_date": payload.get("source_latest_date"),
            }
        )
    if report["status"] != "OK" and report.get("error_message"):
        stack_payload["warnings"] = list(stack_payload.get("warnings", [])) + [report["error_message"]]
    return {"step": report, "metadata": stack_payload}


def _run_sector_board() -> dict[str, object]:
    step = {
        "name": "build_sector_board",
        "script": "scripts/build_sector_board.py",
        "outputs": [
            "data/output/sector_board.parquet",
            "data/output/sector_board.csv",
            "data/output/sector_leaders.parquet",
            "data/output/sector_leaders.csv",
            "data/output/sector_board_metadata.json",
        ],
    }
    report = _run_step(step)
    metadata_path = PROJECT_ROOT / "data/output/sector_board_metadata.json"
    sector_payload = _build_sector_board_metadata(
        enabled=True,
        status=report["status"],
        latest_date=None,
        n_sectors=0,
        generated_files=[],
        warnings=[],
    )
    if metadata_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        sector_payload.update(
            {
                "status": payload.get("status", report["status"]),
                "latest_date": payload.get("latest_date"),
                "n_sectors": payload.get("n_sectors", 0),
                "total_symbols": payload.get("total_symbols"),
                "mapped_symbols": payload.get("mapped_symbols"),
                "missing_symbols": payload.get("missing_symbols"),
                "generated_files": payload.get("generated_files", []),
                "warnings": payload.get("warnings", []),
                "sector_map_source": payload.get("sector_map_source"),
                "mapping_coverage": payload.get("mapping_coverage"),
                "unknown_ratio": payload.get("unknown_ratio"),
            }
        )
    if report["status"] != "OK" and report.get("error_message"):
        sector_payload["warnings"] = list(sector_payload.get("warnings", [])) + [report["error_message"]]
    return {"step": report, "metadata": sector_payload}


def _run_cashflow_board() -> dict[str, object]:
    step = {
        "name": "build_cashflow_board",
        "script": "scripts/build_cashflow_board.py",
        "outputs": [
            "data/output/cashflow_board.parquet",
            "data/output/cashflow_board.csv",
            "data/output/sector_cashflow.parquet",
            "data/output/sector_cashflow.csv",
            "data/output/watchlist_cashflow_confirmation.parquet",
            "data/output/watchlist_cashflow_confirmation.csv",
            "data/output/cashflow_board_metadata.json",
        ],
    }
    report = _run_step(step)
    metadata_path = PROJECT_ROOT / "data/output/cashflow_board_metadata.json"
    cashflow_payload = _build_cashflow_board_metadata(
        enabled=True,
        status=report["status"],
        latest_date=None,
        n_symbols=0,
        n_sectors=0,
        value_proxy_used=False,
        n_data_quality_warnings=0,
        n_low_liquidity_symbols=0,
        n_zero_volume_symbols=0,
        confirmation_counts={},
        sector_score_warnings=[],
        generated_files=[],
        warnings=[],
    )
    if metadata_path.exists():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            cashflow_payload.update(
                {
                    "status": payload.get("status", report["status"]),
                    "latest_date": payload.get("latest_date"),
                    "n_symbols": payload.get("n_symbols", 0),
                    "n_sectors": payload.get("n_sectors", 0),
                    "value_proxy_used": payload.get("value_proxy_used", False),
                    "n_data_quality_warnings": payload.get("n_data_quality_warnings", 0),
                    "n_low_liquidity_symbols": payload.get("n_low_liquidity_symbols", 0),
                    "n_zero_volume_symbols": payload.get("n_zero_volume_symbols", 0),
                    "confirmation_counts": payload.get("confirmation_counts", {}),
                    "sector_score_warnings": payload.get("sector_score_warnings", []),
                    "generated_files": payload.get("generated_files", []),
                    "warnings": payload.get("warnings", []),
                }
            )
        except Exception:
            pass
    if report["status"] != "OK" and report.get("error_message"):
        cashflow_payload["warnings"] = list(cashflow_payload.get("warnings", [])) + [report["error_message"]]
    return {"step": report, "metadata": cashflow_payload}


def _run_research_notes() -> dict[str, object]:
    step = {
        "name": "build_research_notes",
        "script": "scripts/build_research_notes.py",
        "outputs": [
            "data/output/research_notes_index.parquet",
            "data/output/research_notes_index.csv",
            "data/output/research_notes_metadata.json",
        ],
    }
    report = _run_step(step)
    metadata_path = PROJECT_ROOT / "data/output/research_notes_metadata.json"
    notes_payload = _build_research_notes_metadata(
        enabled=True,
        status=report["status"],
        n_notes_generated=0,
        generated_files=[],
        warnings=[],
    )
    if metadata_path.exists():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            notes_payload.update(
                {
                    "status": payload.get("status", report["status"]),
                    "n_notes_generated": payload.get("n_notes_generated", 0),
                    "generated_files": payload.get("generated_files", []),
                    "warnings": payload.get("warnings", []),
                }
            )
        except Exception:
            pass
    if report["status"] != "OK" and report.get("error_message"):
        notes_payload["warnings"] = list(notes_payload.get("warnings", [])) + [report["error_message"]]
    return {"step": report, "metadata": notes_payload}


def _build_research_notes_metadata(
    enabled: bool = False,
    status: str | None = None,
    n_notes_generated: int | None = None,
    generated_files: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"enabled": enabled}
    if enabled:
        payload.update(
            {
                "status": status or "ERROR",
                "n_notes_generated": n_notes_generated or 0,
                "generated_files": generated_files or [],
                "warnings": warnings or [],
            }
        )
    return payload


def _default_research_notes_metadata() -> dict[str, object]:
    return _build_research_notes_metadata(enabled=False)


def _build_pipeline_metadata(
    mode: str,
    steps: list[dict[str, object]],
    freshness: dict[str, object],
    portfolio_stack: dict[str, object] | None = None,
    sector_board: dict[str, object] | None = None,
    cashflow_board: dict[str, object] | None = None,
    research_notes: dict[str, object] | None = None,
    online_update: dict[str, object] | None = None,
    flags_used: list[str] | None = None,
) -> dict[str, object]:
    stock_df = read_parquet(PROJECT_ROOT / "data/processed/stock_features.parquet")
    watchlist_source = resolve_watchlist_source(PROJECT_ROOT)
    watchlist_source_metadata = watchlist_source.metadata()
    watchlist_source_metadata["source_path"] = relative_path(watchlist_source_metadata.get("source_path"), PROJECT_ROOT)
    watchlist_counts = {}
    for name in ("research_candidates", "trading_watchlist", "client_ready_watchlist"):
        path = PROJECT_ROOT / f"data/output/{name}.parquet"
        frame = read_parquet(path)
        watchlist_counts[name] = {
            "rows": int(len(frame)),
            "symbols": int(frame["symbol"].nunique()) if "symbol" in frame.columns else 0,
            "latest_date": dataframe_metadata(frame).get("latest_date"),
        }

    generated_files = []
    for step in steps:
        for artifact in step.get("outputs", []):
            if artifact.get("exists"):
                generated_files.append(artifact["path"])
    generated_files = list(dict.fromkeys(generated_files))

    warnings = list(freshness.get("warnings", []))
    errors = list(freshness.get("errors", []))
    if online_update and online_update.get("warnings"):
        warnings.extend(str(item) for item in online_update.get("warnings", []))

    summary_path = PROJECT_ROOT / "data/output/update_daily_data_summary.json"
    summary_data = {}
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception:
            pass

    sf = freshness.get("symbol_freshness") or {}
    total_uni = sf.get("total_symbols") or watchlist_counts.get("stock_features", {}).get("symbols", 0) or 501
    fresh_cnt = sf.get("symbols_at_baseline_date") or 0
    stale_cnt = sf.get("stale_symbol_count") or 0
    fresh_ratio = 1.0 - (sf.get("stale_symbol_ratio") or 0.0)

    universe_update = {
        "scope": summary_data.get("update_scope") or ("offline" if mode == "offline" else "unknown"),
        "attempted_count": summary_data.get("attempted_count") or 0,
        "succeeded_count": summary_data.get("succeeded_count") or 0,
        "failed_count": summary_data.get("failed_count") or 0,
        "total_universe_count": total_uni,
        "fresh_symbol_count": fresh_cnt,
        "stale_symbol_count": stale_cnt,
        "fresh_coverage_ratio": fresh_ratio,
        "status": summary_data.get("status") or ("OK" if stale_cnt == 0 else "WARNING")
    }

    payload = {
        "run_timestamp": utc_now_iso(),
        "run_mode": mode,
        "flags_used": flags_used or [],
        "latest_stock_date": dataframe_metadata(stock_df).get("latest_date"),
        "latest_feature_date": dataframe_metadata(stock_df).get("latest_date"),
        "latest_benchmark_date": freshness.get("artifacts", {}).get("benchmark_vnindex", {}).get("latest_date"),
        "total_symbols": int(stock_df["symbol"].nunique()) if "symbol" in stock_df.columns else 0,
        "total_rows": int(len(stock_df)),
        "watchlist_source": watchlist_source_metadata,
        "watchlist_counts": watchlist_counts,
        "warnings": warnings,
        "errors": errors,
        "freshness_status": freshness.get("status"),
        "benchmark_status": _benchmark_status(freshness),
        "symbol_freshness": freshness.get("symbol_freshness"),
        "universe_update": universe_update,
        "generated_files": generated_files,
        "portfolio_stack": portfolio_stack or _default_portfolio_stack_metadata(),
        "sector_board": sector_board or _default_sector_board_metadata(),
        "cashflow_board": cashflow_board or _default_cashflow_board_metadata(),
        "research_notes": research_notes or _default_research_notes_metadata(),
        "online_update": online_update or _build_online_update_metadata(enabled=False),
        "steps": steps,
    }
    validate_pipeline_metadata(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the daily research pipeline in offline or online mode.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--offline", action="store_true", help="Use existing parquet data only.")
    group.add_argument("--online", action="store_true", help="Fetch fresh SSI data before rebuilding artifacts.")
    parser.add_argument("--strict-freshness", action="store_true", help="Treat stale warning-level artifacts as errors.")
    parser.add_argument("--build-sector", action="store_true", help="Build sector board outputs after watchlists are available.")
    parser.add_argument("--build-portfolio", action="store_true", help="Build portfolio/risk/capital outputs after watchlists.")
    parser.add_argument("--build-cashflow", action="store_true", help="Deprecated no-op: cashflow board now builds by default (audit F1).")
    parser.add_argument("--skip-cashflow", action="store_true", help="Skip the full cashflow board + confirmation build after watchlists.")
    parser.add_argument("--build-research-notes", action="store_true", help="Build research notes after watchlists, cashflow and portfolio.")
    parser.add_argument("--update-index", action="store_true", help="Refresh raw index/VNINDEX data before generating features in online mode.")
    parser.add_argument("--update-scope", default="core", choices=["core", "full", "batch", "custom"], help="Scope for updating daily data.")
    parser.add_argument("--batch-id", type=int, default=0, help="Batch ID (for batch scope).")
    parser.add_argument("--batch-count", type=int, default=10, help="Total batches (for batch scope).")
    parser.add_argument("--update-symbols", type=str, help="Comma-separated symbols (for custom scope).")
    parser.add_argument("--workers", type=int, help="Override concurrent workers.")
    args = parser.parse_args(argv)

    mode = "online" if args.online else "offline"
    flags_used = [flag for flag, enabled in [
        ("--online", args.online),
        ("--offline", args.offline or not args.online),
        ("--strict-freshness", args.strict_freshness),
        ("--build-sector", args.build_sector),
        ("--build-portfolio", args.build_portfolio),
        ("--build-cashflow", args.build_cashflow),
        ("--skip-cashflow", args.skip_cashflow),
        ("--build-research-notes", args.build_research_notes),
        ("--update-index", args.update_index),
    ] if enabled]
    if args.update_scope:
        flags_used.append(f"--update-scope {args.update_scope}")
    if args.batch_id != 0:
        flags_used.append(f"--batch-id {args.batch_id}")
    if args.batch_count != 10:
        flags_used.append(f"--batch-count {args.batch_count}")
    if args.update_symbols:
        flags_used.append(f"--update-symbols {args.update_symbols}")
    if args.workers:
        flags_used.append(f"--workers {args.workers}")

    if mode == "online":
        _ensure_online_ready()
    steps_to_run = _resolve_steps_to_run(mode=mode, update_index=args.update_index)

    LOGGER.info("Starting daily pipeline in `%s` mode", mode)
    step_reports: list[dict[str, object]] = []
    online_update_metadata = _build_online_update_metadata(enabled=(mode == "online"))
    for step in steps_to_run:
        report = _run_step(step, args_context=args)
        if mode == "online" and report["name"] == "update_daily_data":
            summary_path = Path("data/output/update_daily_data_summary.json")
            if summary_path.exists():
                import json
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary_data = json.load(f)
                    failed_syms = summary_data.get("failed_symbols", [])
                    if failed_syms:
                        report["status"] = "WARNING"
                        report["error_category"] = "PROVIDER_RATE_LIMIT_PARTIAL"
                        report["error_message"] = f"Failed to update symbols: {', '.join(failed_syms)}"
                        report["recommended_action"] = "Rerun online update later or use offline mode if cached data is acceptable."
                        online_update_metadata["failed_symbols"] = failed_syms
                except Exception as e:
                    LOGGER.warning("Could not read update_daily_data_summary.json: %s", e)
        step_reports.append(report)
        if mode == "online" and report["name"] in ONLINE_STEP_NAMES:
            online_update_metadata["steps"].append(
                {
                    "name": report["name"],
                    "status": report["status"],
                    "error_category": report.get("error_category"),
                    "error_message": report.get("error_message"),
                    "recommended_action": report.get("recommended_action"),
                }
            )
            if report["status"] == "WARNING":
                online_update_metadata.update(
                    {
                        "status": "PARTIAL_OK",
                        "error_category": report.get("error_category"),
                        "error_message": report.get("error_message"),
                        "recommended_action": report.get("recommended_action"),
                    }
                )
                if report.get("error_message"):
                    online_update_metadata["warnings"].append(f"{report['name']}: {report['error_message']}")
                continue
        if report["status"] != "OK":
            error_category = str(report.get("error_category") or "UNKNOWN_ERROR")
            error_message = report.get("error_message")
            if mode == "online" and report["name"] in ONLINE_STEP_NAMES and error_category in TOLERABLE_ONLINE_ERROR_CATEGORIES:
                online_update_metadata.update(
                    {
                        "status": "WARNING",
                        "error_category": error_category,
                        "error_message": error_message,
                        "recommended_action": report.get("recommended_action"),
                    }
                )
                if error_message:
                    online_update_metadata["warnings"].append(f"{report['name']}: {error_message}")
                LOGGER.warning(
                    "Online step `%s` failed with %s. Continuing with local data.",
                    report["name"],
                    error_category,
                )
                continue

            if mode == "online" and report["name"] in ONLINE_STEP_NAMES:
                online_update_metadata.update(
                    {
                        "status": "ERROR",
                        "error_category": error_category,
                        "error_message": error_message,
                        "recommended_action": report.get("recommended_action"),
                    }
                )
            metadata = _build_pipeline_metadata(
                mode=mode,
                steps=step_reports,
                freshness={"status": "ERROR", "warnings": [], "errors": [error_message or "Unknown error"], "artifacts": {}},
                portfolio_stack=_default_portfolio_stack_metadata(),
                online_update=online_update_metadata,
                flags_used=flags_used,
            )
            write_json(metadata, PROJECT_ROOT / "data/output/pipeline_metadata.json")
            snapshot_path = write_run_snapshot(metadata, PROJECT_ROOT)
            metadata["generated_files"] = list(dict.fromkeys(metadata["generated_files"] + [relative_path(snapshot_path, PROJECT_ROOT)]))
            write_json(metadata, PROJECT_ROOT / "data/output/pipeline_metadata.json")
            LOGGER.error("Pipeline stopped at step `%s`", step["name"])
            return 1

    freshness = evaluate_freshness(base_dir=PROJECT_ROOT, strict=args.strict_freshness, scope=args.update_scope)
    sector_board_metadata = _default_sector_board_metadata()
    if args.build_sector:
        sector_result = _run_sector_board()
        step_reports.append(sector_result["step"])
        sector_board_metadata = sector_result["metadata"]

    cashflow_board_metadata = _default_cashflow_board_metadata()
    if not args.skip_cashflow:
        cashflow_result = _run_cashflow_board()
        step_reports.append(cashflow_result["step"])
        cashflow_board_metadata = cashflow_result["metadata"]

    portfolio_stack_metadata = _default_portfolio_stack_metadata()
    if args.build_portfolio:
        if freshness["status"] == "ERROR":
            portfolio_stack_metadata = {
                **_build_portfolio_stack_metadata(
                    enabled=True,
                    status="ERROR",
                    warnings=["Skipped portfolio stack because freshness check returned ERROR."],
                    generated_files=[],
                    source_watchlist=None,
                    symbols_used=[],
                ),
            }
        else:
            stack_result = _run_portfolio_stack()
            step_reports.append(stack_result["step"])
            portfolio_stack_metadata = stack_result["metadata"]

    research_notes_metadata = _default_research_notes_metadata()
    if args.build_research_notes:
        notes_result = _run_research_notes()
        step_reports.append(notes_result["step"])
        research_notes_metadata = notes_result["metadata"]

    metadata = _build_pipeline_metadata(
        mode=mode,
        steps=step_reports,
        freshness=freshness,
        portfolio_stack=portfolio_stack_metadata,
        sector_board=sector_board_metadata,
        cashflow_board=cashflow_board_metadata,
        research_notes=research_notes_metadata,
        online_update=online_update_metadata,
        flags_used=flags_used,
    )
    write_json(metadata, PROJECT_ROOT / "data/output/pipeline_metadata.json")
    snapshot_path = write_run_snapshot(metadata, PROJECT_ROOT)
    metadata["generated_files"] = list(dict.fromkeys(metadata["generated_files"] + [relative_path(snapshot_path, PROJECT_ROOT)]))
    write_json(metadata, PROJECT_ROOT / "data/output/pipeline_metadata.json")

    LOGGER.info("Daily pipeline complete with freshness status: %s", freshness["status"])
    if freshness["status"] == "ERROR":
        return 1
    if args.build_sector and sector_board_metadata.get("status") == "ERROR":
        return 1
    if not args.skip_cashflow and cashflow_board_metadata.get("status") == "ERROR":
        return 1
    if args.build_portfolio and portfolio_stack_metadata.get("status") == "ERROR":
        return 1
    if args.build_research_notes and research_notes_metadata.get("status") == "ERROR":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
