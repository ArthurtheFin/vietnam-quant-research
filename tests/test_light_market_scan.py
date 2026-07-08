import pandas as pd

from src.screening.light_market_scan import (
    latest_light_scan_snapshot,
    prepare_light_market_scan_features,
    select_auto_watchlist,
)


def test_light_market_scan_builds_ranked_snapshot():
    dates = pd.date_range("2025-01-01", periods=160, freq="D")
    rows = []
    # Prices are raw VND (audit C1: min_price is 10,000 VND, not a bare "10.0").
    specs = [
        ("AAA", "Banking", 100_000.0, 12_000_000_000.0),
        ("BBB", "Securities", 50_000.0, 15_000_000_000.0),
        ("CCC", "Retail", 40_000.0, 9_000_000_000.0),
    ]
    for symbol, sector, base, value in specs:
        for i, d in enumerate(dates):
            rows.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "date": d,
                    "open": base + i * 80.0,
                    "high": base + i * 80.0 + 150.0,
                    "low": base + i * 80.0 - 100.0,
                    "close": base + i * 80.0 + (i % 7) * 10.0,
                    "volume": 1_000_000 + i * 500,
                    "value": value + i * 10_000_000,
                }
            )
    df = pd.DataFrame(rows)
    features = prepare_light_market_scan_features(df)
    snapshot = latest_light_scan_snapshot(features)

    assert not snapshot.empty
    assert "light_scan_score" in snapshot.columns
    assert snapshot["liquidity_pass"].all()


def test_select_auto_watchlist_respects_sector_cap():
    snapshot = pd.DataFrame(
        {
            "symbol": ["AAA", "AAB", "AAC", "BBB", "BBC"],
            "sector": ["Banking", "Banking", "Banking", "Retail", "Retail"],
            "light_scan_score": [90, 85, 80, 88, 82],
            "avg_value_20d": [20, 19, 18, 17, 16],
        }
    )
    top = select_auto_watchlist(snapshot, top_n=3, max_per_sector=1)

    assert len(top) == 2
    assert top["sector"].nunique() == 2


def test_light_market_scan_filters_out_non_primary_symbols():
    dates = pd.date_range("2025-01-01", periods=140, freq="D")
    rows = []
    for symbol in ["AAA", "CFPT2529"]:
        for i, d in enumerate(dates):
            rows.append(
                {
                    "symbol": symbol,
                    "sector": "Tech",
                    "date": d,
                    "open": 10 + i * 0.1,
                    "high": 10.5 + i * 0.1,
                    "low": 9.5 + i * 0.1,
                    "close": 10 + i * 0.1,
                    "volume": 1_000_000,
                    "value": 12_000_000_000.0,
                }
            )

    features = prepare_light_market_scan_features(pd.DataFrame(rows))

    assert set(features["symbol"].unique()) == {"AAA"}
