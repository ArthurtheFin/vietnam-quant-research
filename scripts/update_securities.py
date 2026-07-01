from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from src.data.ssi_client import SSIDataClient
from src.data.loaders import save_parquet

client = SSIDataClient()
with open('config/strategy_config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

for market in cfg.get('universe', {}).get('markets', []):
    df = client.get_securities(market)
    save_parquet(df, Path('data/raw/securities') / f'{market}.parquet')
    print(market, df.shape)
