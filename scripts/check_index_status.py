from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


def safe_count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(pd.read_parquet(path))
    except Exception:
        return -1


raw_index_path = Path("data/raw/index_ohlcv/VNINDEX.parquet")
processed_benchmark_path = Path("data/processed/benchmark_vnindex.parquet")
processed_index_features_path = Path("data/processed/index_features.parquet")

try:
    import ssi_fc_data  # noqa: F401
    ssi_pkg_status = "installed"
except Exception:
    ssi_pkg_status = "missing"

summary = {
    "ssi_fc_data_package": ssi_pkg_status,
    "raw_vnindex_exists": raw_index_path.exists(),
    "raw_vnindex_rows": safe_count_rows(raw_index_path),
    "processed_benchmark_exists": processed_benchmark_path.exists(),
    "processed_benchmark_rows": safe_count_rows(processed_benchmark_path),
    "processed_index_features_exists": processed_index_features_path.exists(),
    "processed_index_features_rows": safe_count_rows(processed_index_features_path),
}

for key, value in summary.items():
    print(f"{key}: {value}")

if ssi_pkg_status != "installed":
    print("Thiếu package SSI FCData. Hãy cài package trước khi fetch index live.")
elif not raw_index_path.exists():
    print("Chưa có raw VNINDEX. Hãy chạy: python scripts/update_index_data.py")
elif not processed_benchmark_path.exists():
    print("Đã có raw VNINDEX nhưng chưa có benchmark processed. Hãy chạy: python scripts/generate_features.py")
else:
    print("Hệ thống benchmark VNINDEX đã sẵn sàng.")
