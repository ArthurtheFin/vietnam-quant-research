from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv


load_dotenv(PROJECT_ROOT / ".env")

required_env = [
    "SSI_CONSUMER_ID",
    "SSI_CONSUMER_SECRET",
    "SSI_URL",
    "SSI_STREAM_URL",
]

print("python_executable:", sys.executable)

try:
    import ssi_fc_data  # noqa: F401
    print("ssi_fc_data_package: installed")
except Exception as exc:
    print("ssi_fc_data_package: missing")
    print("import_error:", f"{type(exc).__name__}: {exc}")

env_path = PROJECT_ROOT / ".env"
print("env_file_exists:", env_path.exists())

for key in required_env:
    value = os.getenv(key)
    status = "set" if value else "missing"
    print(f"{key}: {status}")

print("\nNext steps:")
print("1. If package is missing: python scripts/install_ssi_fcdata.py /path/to/ssi_fc_data-2.2.2.tar.gz")
print("2. If env vars are missing: fill .env from .env.example")
print("3. Then run: python scripts/update_index_data.py")
