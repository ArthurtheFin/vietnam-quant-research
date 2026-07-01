import sys
from pathlib import Path
import json
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.ssi_client import SSIDataClient
from src.data import fcdata_config as config
from src.data.ssi_client import model

client = SSIDataClient()

for label, start, end in [
    ("90 days", "01/01/2023", "31/03/2023"),
    ("180 days", "01/01/2023", "30/06/2023"),
    ("365 days", "01/01/2023", "31/12/2023"),
    ("730 days (2 years)", "01/01/2022", "31/12/2023"),
    ("1800 days (5 years)", "01/01/2019", "31/12/2023")
]:
    time.sleep(1.5) # Sleep to avoid 429
    req = model.daily_ohlc("AAA", start, end, 1, 1000, True)
    try:
        raw = client.client.daily_ohlc(config, req)
        if isinstance(raw, str):
            res = json.loads(raw)
        else:
            res = raw
        print(f"\n{label} ({start} -> {end}):")
        if isinstance(res, dict):
            print("Status:", res.get("status"))
            print("Message:", res.get("message"))
            data = res.get("data")
            if isinstance(data, list):
                print("Data length:", len(data))
            else:
                print("Data type:", type(data))
    except Exception as e:
        print(f"{label} failed with: {e}")
