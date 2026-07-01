import concurrent.futures
from datetime import date, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import yaml
import pandas as pd
from src.data.fetch_daily import update_symbol_history

with open('config/strategy_config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

start_date = cfg.get('universe', {}).get('start_date', '2020-01-01')
END_DATE = date.today().strftime('%Y-%m-%d')

try:
    from src.data.ssi_client import SSIDataClient
except ImportError as exc:
    raise SystemExit(
        "Khong the import `ssi_fc_data`. Hay cai package SSI FCData truoc khi chay update_daily_data.py"
    ) from exc

client = SSIDataClient()
watchlist = cfg.get('universe', {}).get('watchlist', [])

if not watchlist:
    print("Warning: No watchlist found in config/strategy_config.yaml under universe.watchlist")

# 1. Detect the latest trading date from the market using VNINDEX
market_latest_date = None
try:
    three_days_ago = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    vnindex_df = client.get_daily_ohlc("VNINDEX", from_date=three_days_ago, to_date=END_DATE)
    if not vnindex_df.empty:
        date_col = "tradingdate" if "tradingdate" in vnindex_df.columns else ("date" if "date" in vnindex_df.columns else vnindex_df.columns[0])
        market_latest_date = pd.to_datetime(vnindex_df[date_col], dayfirst=True).max()
        print(f"Latest market trading date detected: {market_latest_date.strftime('%Y-%m-%d')}")
except Exception as e:
    print(f"Warning: Could not detect latest market date: {e}. Defaulting to incremental update.")

# 2. Parallel fetch using ThreadPoolExecutor
def fetch_worker(symbol):
    try:
        df = update_symbol_history(
            client=client,
            symbol=symbol,
            start_date=start_date,
            end_date=END_DATE,
            request_sleep=0.4,
            market_latest_date=market_latest_date
        )
        return symbol, df.shape
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return symbol, None

print(f"\nUpdating {len(watchlist)} symbols using 3 parallel workers...")
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    # Use list() to block until all threads are completed
    results = list(executor.map(fetch_worker, watchlist))

print("\n=== Update Results ===")
updated_count = 0
for symbol, shape in results:
    if shape is not None:
        print(f"{symbol}: {shape[0]} rows")
        updated_count += 1
    else:
        print(f"{symbol}: FAILED")

print(f"\n=== Updated {updated_count}/{len(watchlist)} symbols ===")

