from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd
from src.data.loaders import read_parquet


def _format_table(df: pd.DataFrame, cols: list[str]) -> str:
    """Format DataFrame as aligned text table without tabulate dependency."""
    available = [c for c in cols if c in df.columns]
    if not available:
        return "(no data)"
    sub = df[available].copy()
    # Format numeric columns
    for col in sub.columns:
        if sub[col].dtype in ('float64', 'float32'):
            sub[col] = sub[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
        else:
            sub[col] = sub[col].astype(str)

    # Calculate column widths
    widths = {col: max(len(col), sub[col].str.len().max()) for col in sub.columns}
    header = " | ".join(col.ljust(widths[col]) for col in sub.columns)
    separator = "-|-".join("-" * widths[col] for col in sub.columns)
    rows = []
    for _, row in sub.iterrows():
        rows.append(" | ".join(str(row[col]).ljust(widths[col]) for col in sub.columns))
    return "\n".join([header, separator] + rows)


signals = read_parquet('data/signals/setup_signals.parquet')
final_watchlist = read_parquet('data/signals/final_watchlist.parquet')
meta_watchlist = read_parquet('data/signals/meta_ranking_watchlist.parquet')
stealth_watchlist = read_parquet('data/signals/stealth_accumulation_watchlist.parquet')

Path('data/reports').mkdir(parents=True, exist_ok=True)

body_parts = ['# Daily Quant Note\n']

# Section 1: Active Signals
if not signals.empty:
    latest_date = signals['date'].max()
    latest = signals[signals['date'] == latest_date]
    signal_cols = [c for c in ['breakout_20d', 'pullback_ma20', 'volume_spike'] if c in latest.columns]
    if signal_cols:
        active = latest[latest[signal_cols].fillna(False).any(axis=1)].copy()
    else:
        active = latest.copy()

    if active.empty:
        body_parts.append(f'**Date: {latest_date}** — No active setups.\n')
    else:
        cols = [c for c in ['symbol', 'date', 'breakout_20d', 'pullback_ma20', 'volume_spike', 'return_1d', 'volume_zscore_20d'] if c in active.columns]
        body_parts.append(f'## Active Setups ({latest_date})\n')
        body_parts.append('```')
        body_parts.append(_format_table(active, cols))
        body_parts.append('```\n')
else:
    body_parts.append('No signals data found.\n')

# Section 2: Final Watchlist
if not final_watchlist.empty:
    final_cols = [
        'rank', 'symbol', 'close', 'final_score', 'trend_score', 'momentum_score',
        'relative_strength_score', 'liquidity_score', 'risk_score', 'signal_score',
        'volatility_regime', 'reason', 'warning'
    ]
    body_parts.append('## Final Watchlist (Top 10)\n')
    body_parts.append('```')
    body_parts.append(_format_table(final_watchlist.head(10), final_cols))
    body_parts.append('```\n')

# Section 3: Meta Ranking Watchlist
if not meta_watchlist.empty:
    meta_cols = ['meta_rank', 'symbol', 'meta_score', 'priority_bucket', 'setup_style',
                 'trade_edge_score', 'net_accumulation_score', 'momentum_component_score', 'risk_penalty_score']
    body_parts.append('## Meta Ranking Watchlist\n')
    body_parts.append('```')
    body_parts.append(_format_table(meta_watchlist.head(10), meta_cols))
    body_parts.append('```\n')

# Section 4: Stealth Accumulation Watchlist
if not stealth_watchlist.empty:
    stealth_cols = ['symbol', 'accumulation_stage', 'net_accumulation_score',
                    'accumulation_score', 'breakout_quality_score', 'fakeout_risk_score']
    body_parts.append('## Stealth Accumulation Watchlist\n')
    body_parts.append('```')
    body_parts.append(_format_table(stealth_watchlist.head(10), stealth_cols))
    body_parts.append('```\n')

report = '\n'.join(body_parts)
Path('data/reports/daily_market_note.md').write_text(report, encoding='utf-8')
print('Generated data/reports/daily_market_note.md')
