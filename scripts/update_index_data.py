from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
import pandas as pd

import os
os.chdir(PROJECT_ROOT)

from src.data.benchmark import build_benchmark_file, load_index_files, prepare_index_features
from src.data.fetch_index import update_index_history
from src.data.loaders import save_parquet
from src.utils.pipeline_io import relative_path

with open("config/strategy_config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

START_DATE = cfg.get('universe', {}).get('start_date', '2020-01-01')
END_DATE = date.today().strftime("%Y-%m-%d")

def main() -> int:
    try:
        from src.data.ssi_client import SSIDataClient, SSIEmptyResponseError, SSIRateLimitError
    except ImportError as exc:
        raise SystemExit(
            "Khong the import `ssi_fc_data`. Hay cai package SSI FCData truoc khi chay update_index_data.py"
        ) from exc

    indexes = cfg.get('universe', {}).get('indexes', [])
    if not indexes:
        raise SystemExit("Khong co index nao trong config/strategy_config.yaml")

    try:
        client = SSIDataClient()
    except EnvironmentError as exc:
        raise SystemExit(str(exc)) from exc

    updated_latest: dict[str, str | None] = {}
    raw_paths: dict[str, str] = {}

    try:
        for index_id in indexes:
            df = update_index_history(client, index_id, START_DATE, END_DATE)
            latest = None
            if not df.empty and "date" in df.columns:
                latest = str(pd.to_datetime(df["date"], errors="coerce").max().date())
            raw_path = Path("data/raw/index_ohlcv") / f"{str(index_id).upper()}.parquet"
            updated_latest[str(index_id).upper()] = latest
            raw_paths[str(index_id).upper()] = relative_path(raw_path, PROJECT_ROOT) or str(raw_path)
            print(f"{str(index_id).upper()} rows={df.shape[0]} latest_raw_date={latest} path={raw_paths[str(index_id).upper()]}")

        index_raw = load_index_files("data/raw/index_ohlcv")
        if index_raw.empty:
            raise SSIEmptyResponseError("Khong co raw index data sau khi fetch.")

        index_features = prepare_index_features(index_raw)
        save_parquet(index_features, "data/processed/index_features.parquet")
        print("index_features", index_features.shape)

        for index_id in indexes:
            benchmark = build_benchmark_file(
                index_id=index_id,
                raw_dir="data/raw/index_ohlcv",
                output_path=f"data/processed/benchmark_{str(index_id).lower()}.parquet",
            )
            latest_benchmark = None
            if not benchmark.empty and "date" in benchmark.columns:
                latest_benchmark = str(pd.to_datetime(benchmark["date"], errors="coerce").max().date())
            print(
                f"benchmark_{str(index_id).lower()} rows={benchmark.shape[0]} latest_benchmark_date={latest_benchmark}"
            )
    except SSIRateLimitError as exc:
        print(f"[PROVIDER_RATE_LIMIT] {exc}")
        return 1
    except SSIEmptyResponseError as exc:
        print(f"[PROVIDER_EMPTY_RESPONSE] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
