from pathlib import Path

import pandas as pd
import pytest

from src.data.fetch_index import standardize_index, update_index_history


class FakeIndexClient:
    def __init__(self, frames: list[pd.DataFrame]):
        self.frames = frames
        self.calls: list[tuple[str, str, str]] = []

    def get_daily_index_chunked(self, index_id: str, start_date: str, end_date: str):
        self.calls.append((index_id, start_date, end_date))
        if not self.frames:
            return pd.DataFrame()
        return self.frames.pop(0)


def test_standardize_index_normalizes_schema():
    raw = pd.DataFrame(
        {
            "tradingdate": ["01/01/2024", "02/01/2024"],
            "indexcode": ["VNINDEX", "VNINDEX"],
            "indexvalue": [1000, 1010],
            "allqty": [100, 120],
            "allvalue": [100000, 121200],
        }
    )
    out = standardize_index(raw)
    assert {"date", "symbol", "close", "volume", "value"}.issubset(out.columns)
    assert out["symbol"].eq("VNINDEX").all()
    assert list(out["date"]) == sorted(out["date"].tolist())


def test_update_index_history_appends_recent_data(tmp_path: Path):
    first = pd.DataFrame(
        {
            "tradingdate": ["01/01/2024", "02/01/2024", "03/01/2024"],
            "indexcode": ["VNINDEX"] * 3,
            "indexvalue": [1000, 1005, 1010],
            "allqty": [100, 100, 100],
            "allvalue": [100000, 100500, 101000],
        }
    )
    second = pd.DataFrame(
        {
            "tradingdate": ["02/01/2024", "03/01/2024", "04/01/2024", "05/01/2024"],
            "indexcode": ["VNINDEX"] * 4,
            "indexvalue": [1005, 1010, 1015, 1020],
            "allqty": [100, 100, 100, 100],
            "allvalue": [100500, 101000, 101500, 102000],
        }
    )
    client = FakeIndexClient([first, second])

    initial = update_index_history(
        client=client,
        index_id="VNINDEX",
        start_date="2024-01-01",
        end_date="2024-01-03",
        output_dir=tmp_path,
        force_refresh=False,
    )
    updated = update_index_history(
        client=client,
        index_id="VNINDEX",
        start_date="2024-01-01",
        end_date="2024-01-05",
        output_dir=tmp_path,
        force_refresh=False,
        refresh_recent_days=2,
    )

    assert len(initial) == 3
    assert len(updated) == 5
    assert updated["symbol"].eq("VNINDEX").all()
    assert len(client.calls) == 2


def test_update_index_history_preserves_existing_file_on_empty_refresh(tmp_path: Path):
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "symbol": ["VNINDEX", "VNINDEX"],
            "close": [1000, 1005],
        }
    )
    existing.to_parquet(tmp_path / "VNINDEX.parquet", index=False)
    client = FakeIndexClient([pd.DataFrame()])

    updated = update_index_history(
        client=client,
        index_id="VNINDEX",
        start_date="2024-01-01",
        end_date="2024-01-05",
        output_dir=tmp_path,
        refresh_recent_days=2,
    )

    reloaded = pd.read_parquet(tmp_path / "VNINDEX.parquet")
    assert len(updated) == 2
    assert len(reloaded) == 2
    assert reloaded["close"].tolist() == [1000, 1005]
