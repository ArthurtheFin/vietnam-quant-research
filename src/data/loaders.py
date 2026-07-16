from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pandas as pd


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, write_fn) -> Path:
    """audit/PATH_TO_100.md mục 10: write to a temp file in the SAME directory
    (so the final os.replace is on one filesystem, guaranteed atomic on
    POSIX) then rename over the target -- a reader (or a daily-update script
    crashing/killed mid-write) never observes a partially-written file at
    `path`, only the old complete version or the new complete version."""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        write_fn(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def save_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    path = ensure_parent(path)
    _atomic_write(path, lambda tmp: df.to_parquet(tmp, index=False))
    return path


def save_csv_atomic(df: pd.DataFrame, path: str | Path, index: bool = False, **to_csv_kwargs) -> Path:
    """Same atomic-write guarantee as save_parquet, for the daily-refreshed
    CSV artifacts (watchlist/report outputs) -- not applied blanket to every
    to_csv() call in the codebase (many are one-off audit/diagnostic dumps
    where this doesn't matter), see NV1b commit for the specific call sites
    this was applied to."""
    path = ensure_parent(path)
    _atomic_write(path, lambda tmp: df.to_csv(tmp, index=index, **to_csv_kwargs))
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
