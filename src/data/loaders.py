from __future__ import annotations

from pathlib import Path
import pandas as pd


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    path = ensure_parent(path)
    df.to_parquet(path, index=False)
    return path


def read_parquet(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def append_parquet(new_df: pd.DataFrame, path: str | Path, subset: list[str] | None = None) -> pd.DataFrame:
    old_df = read_parquet(path)
    if old_df.empty:
        combined = new_df.copy()
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)
    if subset:
        combined = combined.drop_duplicates(subset=subset, keep="last")
    else:
        combined = combined.drop_duplicates(keep="last")
    save_parquet(combined, path)
    return combined


def read_symbol_files(folder: str | Path) -> pd.DataFrame:
    frames = []
    for p in Path(folder).glob("*.parquet"):
        df = pd.read_parquet(p).dropna(axis=1, how="all")
        if not df.empty and not df.dropna(axis=0, how="all").empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
