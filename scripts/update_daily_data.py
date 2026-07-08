import concurrent.futures
from datetime import date, timedelta
from pathlib import Path
import sys

import os
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if "PYTEST_CURRENT_TEST" in os.environ:
    PROJECT_ROOT = Path(os.getcwd())

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "PYTEST_CURRENT_TEST" not in os.environ:
    os.chdir(PROJECT_ROOT)

import pandas as pd
import yaml

from src.data.fetch_daily import update_symbol_history

with open("config/strategy_config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

START_DATE = cfg.get("universe", {}).get("start_date", "2020-01-01")
END_DATE = date.today().strftime("%Y-%m-%d")


def _classify_fetch_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "429" in message or "quota" in message or "rate limit" in message or "exceeded" in message:
        return "PROVIDER_RATE_LIMIT"
    if "expecting value" in message or "empty response" in message:
        return "PROVIDER_EMPTY_RESPONSE"
    return "CODE_ERROR"


def get_full_universe_symbols(base_dir=".") -> list[str]:
    """Real listed universe: union of exchange securities lists (audit B1).

    Reads data/raw/securities/*.parquet produced by scripts/update_securities.py.
    Fails loudly when the lists are missing instead of quietly shrinking the
    universe to whatever was fetched before.
    """
    base = Path(base_dir)
    files = sorted((base / "data/raw/securities").glob("*.parquet"))
    if not files:
        raise SystemExit(
            "No securities lists found in data/raw/securities/. "
            "Run `python scripts/update_securities.py` first (requires SSI FCData credentials), "
            "or use --scope tracked for the previously-fetched symbol set."
        )
    from src.data.validators import filter_primary_equity_symbols

    symbols: set[str] = set()
    for path in files:
        df = pd.read_parquet(path)
        col = next((c for c in df.columns if str(c).lower() == "symbol"), None)
        if col is None:
            raise SystemExit(f"Securities file {path} has no symbol column; refusing to guess.")
        frame = pd.DataFrame({"symbol": df[col].dropna().astype(str).str.upper()})
        frame = filter_primary_equity_symbols(frame)
        symbols.update(frame["symbol"].tolist())
    if not symbols:
        raise SystemExit("Securities lists contained no primary equity symbols.")
    return sorted(symbols)


def get_tracked_universe_symbols(base_dir=".") -> list[str]:
    """Symbols already present in local processed data (the old, self-referential 'full')."""
    base = Path(base_dir)
    for name in ("data/processed/stock_features.parquet", "data/processed/clean_daily_ohlcv.parquet"):
        path = base / name
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty and "symbol" in df.columns:
                    return sorted(list(df["symbol"].dropna().astype(str).unique()))
            except Exception:
                pass
    with open(base / "config/strategy_config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return sorted(cfg.get("universe", {}).get("watchlist", []))


def calculate_freshness_metrics(base_dir=".") -> dict[str, object]:
    base = Path(base_dir)
    ohlcv_path = base / "data/processed/clean_daily_ohlcv.parquet"
    if not ohlcv_path.exists():
        ohlcv_path = base / "data/processed/stock_features.parquet"
    if not ohlcv_path.exists():
        return {"total": 0, "fresh": 0, "stale": 0, "ratio": 0.0}
    try:
        df = pd.read_parquet(ohlcv_path)
        if df.empty or "date" not in df.columns or "symbol" not in df.columns:
            return {"total": 0, "fresh": 0, "stale": 0, "ratio": 0.0}
        df["date"] = pd.to_datetime(df["date"])
        latest_per_symbol = df.groupby("symbol")["date"].max()
        if latest_per_symbol.empty:
            return {"total": 0, "fresh": 0, "stale": 0, "ratio": 0.0}
        baseline = latest_per_symbol.max()
        total = int(latest_per_symbol.index.nunique())
        fresh = int(latest_per_symbol[latest_per_symbol == baseline].count())
        stale = total - fresh
        ratio = float(fresh / total) if total > 0 else 0.0
        return {"total": total, "fresh": fresh, "stale": stale, "ratio": ratio}
    except Exception:
        return {"total": 0, "fresh": 0, "stale": 0, "ratio": 0.0}


def main(argv: list[str] | None = None) -> int:
    import argparse
    from src.validation.freshness_check import ensure_core_universe

    parser = argparse.ArgumentParser(description="Update daily stock price history.")
    parser.add_argument(
        "--scope",
        default="core",
        choices=["core", "tracked", "full", "batch", "custom"],
        help="Update scope. `full`/`batch` use the real listed universe from "
        "data/raw/securities (run update_securities.py first); `tracked` is the "
        "previously-fetched symbol set.",
    )
    parser.add_argument("--batch-id", type=int, default=0, help="Batch ID (for scope=batch).")
    parser.add_argument("--batch-count", type=int, default=10, help="Total batch count (for scope=batch).")
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols (for scope=custom).")
    parser.add_argument("--workers", type=int, help="Number of concurrent workers.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        from src.data.ssi_client import SSIDataClient
    except ImportError as exc:
        raise SystemExit(
            "Khong the import `ssi_fc_data`. Hay cai package SSI FCData truoc khi chay update_daily_data.py"
        ) from exc

    client = SSIDataClient()
    global cfg, START_DATE, END_DATE
    with open("config/strategy_config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    START_DATE = cfg.get("universe", {}).get("start_date", "2020-01-01")

    scope = args.scope
    watchlist = []
    skipped_symbols = []

    if scope == "core":
        watchlist = ensure_core_universe(PROJECT_ROOT)
    elif scope == "tracked":
        watchlist = get_tracked_universe_symbols(PROJECT_ROOT)
    elif scope == "full":
        watchlist = get_full_universe_symbols(PROJECT_ROOT)
    elif scope == "batch":
        full_list = get_full_universe_symbols(PROJECT_ROOT)
        total_count = len(full_list)
        b_count = max(1, args.batch_count)
        b_id = max(0, min(args.batch_id, b_count - 1))
        chunk_size = (total_count + b_count - 1) // b_count
        start_idx = b_id * chunk_size
        end_idx = min(start_idx + chunk_size, total_count)
        watchlist = full_list[start_idx:end_idx]
        skipped_symbols = [s for s in full_list if s not in watchlist]
    elif scope == "custom":
        if not args.symbols:
            print("Error: Scope 'custom' requires --symbols to be specified.")
            return 1
        watchlist = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    if args.workers is not None:
        workers = args.workers
    else:
        workers = 1 if scope == "full" else 3

    request_sleep = 1.2 if scope == "full" else 0.4

    if not watchlist:
        print("Warning: No symbols resolved for update watchlist.")
        return 0

    market_latest_date = None
    try:
        three_days_ago = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        vnindex_df = client.get_daily_ohlc("VNINDEX", from_date=three_days_ago, to_date=END_DATE)
        if not vnindex_df.empty:
            date_col = "tradingdate" if "tradingdate" in vnindex_df.columns else ("date" if "date" in vnindex_df.columns else vnindex_df.columns[0])
            market_latest_date = pd.to_datetime(vnindex_df[date_col], dayfirst=True).max()
            print(f"Latest market trading date detected: {market_latest_date.strftime('%Y-%m-%d')}")
    except Exception as exc:
        print(f"Warning: Could not detect latest market date: {exc}. Defaulting to incremental update.")

    def fetch_worker(symbol):
        try:
            df = update_symbol_history(
                client=client,
                symbol=symbol,
                start_date=START_DATE,
                end_date=END_DATE,
                request_sleep=request_sleep,
                market_latest_date=market_latest_date,
            )
            return {"symbol": symbol, "shape": df.shape, "status": "OK", "error_category": None}
        except Exception as exc:
            category = _classify_fetch_error(exc)
            print(f"[FAILED] SYMBOL: {symbol} Error: {exc} Category: {category}")
            return {"symbol": symbol, "shape": None, "status": "FAILED", "error_category": category}

    print(f"\nUpdating {len(watchlist)} symbols (Scope: {scope}) using {workers} parallel workers...")
    if scope == "full":
        print("WARNING: Updating full universe can take a long time to avoid rate limits.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(fetch_worker, watchlist))

    print("\n=== Update Results ===")
    succeeded_symbols = []
    failed_symbols = []
    for item in results:
        symbol = item["symbol"]
        shape = item["shape"]
        if shape is not None:
            print(f"{symbol}: {shape[0]} rows")
            succeeded_symbols.append(symbol)
        else:
            print(f"{symbol}: [FAILED]")
            failed_symbols.append(symbol)

    status = "OK"
    error_category = None
    recommended_action = None
    if failed_symbols:
        status = "WARNING"
        error_category = "PROVIDER_RATE_LIMIT_PARTIAL"
        recommended_action = "Rerun online update later or use offline mode if cached data is acceptable."

    freshness_metrics = calculate_freshness_metrics(PROJECT_ROOT)
    total_uni_count = freshness_metrics["total"]
    if not total_uni_count:
        if scope in ("full", "batch"):
            total_uni_count = len(get_full_universe_symbols(PROJECT_ROOT))
        else:
            total_uni_count = len(get_tracked_universe_symbols(PROJECT_ROOT))
    coverage = freshness_metrics["ratio"]

    summary = {
        "status": status,
        "update_scope": scope,
        "market_latest_date": market_latest_date.strftime("%Y-%m-%d") if market_latest_date is not None else None,
        "attempted_symbols": watchlist,
        "succeeded_symbols": succeeded_symbols,
        "failed_symbols": failed_symbols,
        "skipped_symbols": skipped_symbols,
        "attempted_count": len(watchlist),
        "succeeded_count": len(succeeded_symbols),
        "failed_count": len(failed_symbols),
        "total_universe_count": total_uni_count,
        "coverage_after_update": coverage,
        "error_category": error_category,
        "recommended_action": recommended_action
    }

    if scope == "batch":
        summary.update({
            "batch_id": args.batch_id,
            "batch_count": args.batch_count,
            "batch_size": len(watchlist)
        })

    import json
    summary_path = Path("data/output/update_daily_data_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== Updated {len(succeeded_symbols)}/{len(watchlist)} symbols (Scope: {scope}) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
