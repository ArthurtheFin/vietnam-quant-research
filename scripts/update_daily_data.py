import concurrent.futures
from datetime import date, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
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


def main() -> int:
    try:
        from src.data.ssi_client import SSIDataClient
    except ImportError as exc:
        raise SystemExit(
            "Khong the import `ssi_fc_data`. Hay cai package SSI FCData truoc khi chay update_daily_data.py"
        ) from exc

    client = SSIDataClient()
    watchlist = cfg.get("universe", {}).get("watchlist", [])

    if not watchlist:
        print("Warning: No watchlist found in config/strategy_config.yaml under universe.watchlist")

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
                request_sleep=0.4,
                market_latest_date=market_latest_date,
            )
            return {"symbol": symbol, "shape": df.shape, "status": "OK", "error_category": None}
        except Exception as exc:
            category = _classify_fetch_error(exc)
            print(f"[{category}] Error fetching {symbol}: {exc}")
            return {"symbol": symbol, "shape": None, "status": "FAILED", "error_category": category}

    print(f"\nUpdating {len(watchlist)} symbols using 3 parallel workers...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch_worker, watchlist))

    print("\n=== Update Results ===")
    updated_count = 0
    failure_categories = set()
    for item in results:
        symbol = item["symbol"]
        shape = item["shape"]
        if shape is not None:
            print(f"{symbol}: {shape[0]} rows")
            updated_count += 1
        else:
            print(f"{symbol}: FAILED")
            if item["error_category"]:
                failure_categories.add(item["error_category"])

    print(f"\n=== Updated {updated_count}/{len(watchlist)} symbols ===")
    if failure_categories:
        print(f"[{sorted(failure_categories)[0]}] update_daily_data encountered failed symbols.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
