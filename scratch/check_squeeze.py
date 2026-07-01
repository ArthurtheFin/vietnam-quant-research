import pandas as pd
import numpy as np
from src.screening.stealth_accumulation import run_stealth_accumulation_screen

dates = pd.date_range("2024-01-01", periods=100, freq="D")
aaa_close = [100.0 + 0.1 * np.sin(i) for i in range(len(dates))]

price_df = pd.DataFrame(
    {
        "symbol": ["AAA"] * len(dates),
        "market": ["HOSE"] * len(dates),
        "date": list(dates),
        "open": aaa_close,
        "high": [c + 0.2 for c in aaa_close],
        "low": [c - 0.2 for c in aaa_close],
        "close": aaa_close,
        "volume": [1_000_000] * len(dates),
    }
)
price_df["value"] = price_df["close"] * price_df["volume"]

config = {
    "filters": {
        "min_price": 10.0,
        "min_avg_value_20d": 500_000.0,
        "trend_filters": {
            "require_above_ma50": False,
            "require_above_ma200": False,
        }
    },
    "thresholds": {
        "stage_a_min_score": 30.0,
        "stage_b_min_score": 40.0,
        "stage_c_min_score": 50.0,
        "watchlist_min_net_score": 30.0,
        "max_fakeout_risk": 90.0,
    }
}

screen = run_stealth_accumulation_screen(price_df=price_df, config=config)
latest = screen[screen["date"] == screen["date"].max()].iloc[0]

print("latest features:")
print("history_pass:", latest["history_pass"])
print("liquidity_pass:", latest["liquidity_pass"])
print("regime_pass:", latest["regime_pass"])
print("trend_pass:", latest["trend_pass"])
print("is_compressed:", latest["is_compressed"])
print("fakeout_risk_score:", latest["fakeout_risk_score"])
print("max_fakeout_risk:", config["thresholds"]["max_fakeout_risk"])
print("accumulation_stage:", latest["accumulation_stage"])
