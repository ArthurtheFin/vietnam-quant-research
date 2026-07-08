from __future__ import annotations

import numpy as np
import pandas as pd


def filter_non_overlapping_signals(
    df: pd.DataFrame,
    signal_col: str,
    holding_period: int = 20,
) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    selected_indices: list[int] = []

    for _, group in out.groupby("symbol"):
        group = group.reset_index()
        last_signal_pos = -10**9

        for i, row in group.iterrows():
            if bool(row.get(signal_col, False)) and i - last_signal_pos > holding_period:
                selected_indices.append(int(row["index"]))
                last_signal_pos = i

    result = out.loc[selected_indices].copy()
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def summarize_trades(df: pd.DataFrame, return_col: str = "net_return") -> dict:
    if df.empty:
        return {
            "trades": 0,
            "win_rate": np.nan,
            "avg_return": np.nan,
            "median_return": np.nan,
            "best_return": np.nan,
            "worst_return": np.nan,
            "gross_profit": np.nan,
            "gross_loss": np.nan,
            "profit_factor": np.nan,
            "stop_rate": np.nan,
        }

    wins = df.loc[df[return_col] > 0, return_col]
    losses = df.loc[df[return_col] < 0, return_col]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    return {
        "trades": int(len(df)),
        "win_rate": float((df[return_col] > 0).mean()),
        "avg_return": float(df[return_col].mean()),
        "median_return": float(df[return_col].median()),
        "best_return": float(df[return_col].max()),
        "worst_return": float(df[return_col].min()),
        "gross_profit": float(gross_profit),
        "gross_loss": float(gross_loss),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss != 0 else float(np.inf),
        "stop_rate": float((df.get("exit_reason", pd.Series(index=df.index)) == "stop_loss").mean()),
    }


def summarize_trades_by_group(
    trades: pd.DataFrame,
    group_col: str,
    return_col: str = "net_return",
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    rows = []
    for value, group in trades.groupby(group_col):
        row = {group_col: value}
        row.update(summarize_trades(group, return_col=return_col))
        rows.append(row)

    return pd.DataFrame(rows).sort_values("profit_factor", ascending=False).reset_index(drop=True)


def backtest_entries_with_fixed_stop(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    holding_period: int = 20,
    stop_loss: float | None = -0.10,
    cost: float = 0.004,
    price_col: str = "close",
    low_col: str = "low",
    high_col: str = "high",
    open_col: str = "open",
) -> pd.DataFrame:
    trades: list[dict] = []

    entries = entries_df.copy()
    prices = price_df.copy()

    entries["date"] = pd.to_datetime(entries["date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values(["symbol", "date"]).copy()

    for _, entry in entries.iterrows():
        symbol = entry["symbol"]
        entry_date = pd.to_datetime(entry["date"])

        symbol_prices = prices[prices["symbol"] == symbol].sort_values("date").reset_index(drop=True)
        match_idx = symbol_prices.index[symbol_prices["date"] == entry_date]
        if len(match_idx) == 0:
            continue

        i = int(match_idx[0])
        if i + 1 >= len(symbol_prices):
            continue

        # I4: enter at the NEXT session's open — the close that produced the
        # signal is not tradeable. Fallback to next close when open is missing.
        entry_row = symbol_prices.loc[i + 1]
        entry_price = entry_row[open_col] if open_col in symbol_prices.columns and pd.notna(entry_row.get(open_col)) else entry_row[price_col]
        future = symbol_prices.loc[i + 1 : i + holding_period].copy()
        if future.empty or pd.isna(entry_price) or entry_price <= 0:
            continue

        future["close_return"] = future[price_col] / entry_price - 1
        future["low_return"] = future[low_col] / entry_price - 1 if low_col in future.columns else future["close_return"]
        future["high_return"] = future[high_col] / entry_price - 1 if high_col in future.columns else future["close_return"]

        exit_reason = "time_exit"
        exit_row = future.iloc[-1]
        gross_return = float(exit_row[price_col] / entry_price - 1)
        exit_price = float(exit_row[price_col])

        if stop_loss is not None:
            # Conservative: stop takes priority when both could trigger on same bar
            stop_hit = future[future["low_return"] <= stop_loss]
            if len(stop_hit) > 0:
                exit_reason = "stop_loss"
                exit_row = stop_hit.iloc[0]
                gross_return = float(stop_loss)
                exit_price = float(entry_price * (1 + stop_loss))

        trades.append(
            {
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": pd.to_datetime(exit_row["date"]),
                "entry_price": float(entry_price),
                "exit_price": exit_price,
                "stop_loss": stop_loss,
                "gross_return": gross_return,
                "net_return": gross_return - cost,
                "mfe": float(future["high_return"].max()),
                "mae": float(future["low_return"].min()),
                "exit_reason": exit_reason,
                "holding_days_realized": int((pd.to_datetime(exit_row["date"]) - entry_date).days),
                "volatility_regime": entry.get("volatility_regime"),
                "volatility_percentile": entry.get("volatility_percentile"),
                "atr_pct_14": entry.get("atr_pct_14"),
            }
        )

    return pd.DataFrame(trades)


def backtest_entries_with_atr_stop(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    atr_col: str = "atr_pct_14",
    atr_multiple: float = 2.0,
    holding_period: int = 20,
    cost: float = 0.004,
    price_col: str = "close",
    low_col: str = "low",
    high_col: str = "high",
    open_col: str = "open",
) -> pd.DataFrame:
    trades: list[dict] = []
    entries = entries_df.copy()
    prices = price_df.copy()

    entries["date"] = pd.to_datetime(entries["date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values(["symbol", "date"]).copy()

    for _, entry in entries.iterrows():
        symbol = entry["symbol"]
        entry_date = pd.to_datetime(entry["date"])
        symbol_prices = prices[prices["symbol"] == symbol].sort_values("date").reset_index(drop=True)
        match_idx = symbol_prices.index[symbol_prices["date"] == entry_date]
        if len(match_idx) == 0:
            continue

        i = int(match_idx[0])
        if i + 1 >= len(symbol_prices):
            continue

        # I4: enter at the NEXT session's open; ATR is taken from the signal bar
        # (information available at decision time).
        entry_row = symbol_prices.loc[i + 1]
        entry_price = entry_row[open_col] if open_col in symbol_prices.columns and pd.notna(entry_row.get(open_col)) else entry_row[price_col]
        atr_pct = symbol_prices.loc[i].get(atr_col, np.nan)
        if pd.isna(entry_price) or entry_price <= 0 or pd.isna(atr_pct):
            continue

        stop_loss = -float(atr_multiple) * float(atr_pct)
        future = symbol_prices.loc[i + 1 : i + holding_period].copy()
        if future.empty:
            continue

        future["close_return"] = future[price_col] / entry_price - 1
        future["low_return"] = future[low_col] / entry_price - 1 if low_col in future.columns else future["close_return"]
        future["high_return"] = future[high_col] / entry_price - 1 if high_col in future.columns else future["close_return"]

        exit_reason = "time_exit"
        exit_row = future.iloc[-1]
        gross_return = float(exit_row[price_col] / entry_price - 1)
        exit_price = float(exit_row[price_col])

        # Conservative: stop takes priority when both could trigger on same bar
        stop_hit = future[future["low_return"] <= stop_loss]
        if len(stop_hit) > 0:
            exit_reason = "atr_stop"
            exit_row = stop_hit.iloc[0]
            gross_return = float(stop_loss)
            exit_price = float(entry_price * (1 + stop_loss))

        trades.append(
            {
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": pd.to_datetime(exit_row["date"]),
                "entry_price": float(entry_price),
                "exit_price": exit_price,
                "atr_multiple": float(atr_multiple),
                "stop_loss": float(stop_loss),
                "gross_return": gross_return,
                "net_return": gross_return - cost,
                "mfe": float(future["high_return"].max()),
                "mae": float(future["low_return"].min()),
                "exit_reason": exit_reason,
                "holding_days_realized": int((pd.to_datetime(exit_row["date"]) - entry_date).days),
                "volatility_regime": entry.get("volatility_regime"),
                "volatility_percentile": entry.get("volatility_percentile"),
                "atr_pct_14": entry.get(atr_col),
            }
        )

    return pd.DataFrame(trades)


def sweep_fixed_stop_losses(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    stop_losses: list[float | None],
    holding_period: int = 20,
    cost: float = 0.004,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    trades_by_stop: dict[float | None, pd.DataFrame] = {}

    for stop_loss in stop_losses:
        trades = backtest_entries_with_fixed_stop(
            entries_df=entries_df,
            price_df=price_df,
            holding_period=holding_period,
            stop_loss=stop_loss,
            cost=cost,
        )
        trades_by_stop[stop_loss] = trades
        row = {"stop_loss": "no_stop" if stop_loss is None else stop_loss}
        row.update(summarize_trades(trades))
        rows.append(row)

    summary = pd.DataFrame(rows).sort_values(["profit_factor", "avg_return"], ascending=[False, False]).reset_index(drop=True)
    return summary, trades_by_stop


def sweep_atr_multiples(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    atr_multiples: list[float],
    atr_col: str = "atr_pct_14",
    holding_period: int = 20,
    cost: float = 0.004,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    trades_by_multiple: dict[float, pd.DataFrame] = {}

    for atr_multiple in atr_multiples:
        trades = backtest_entries_with_atr_stop(
            entries_df=entries_df,
            price_df=price_df,
            atr_col=atr_col,
            atr_multiple=atr_multiple,
            holding_period=holding_period,
            cost=cost,
        )
        trades_by_multiple[atr_multiple] = trades
        row = {"atr_multiple": atr_multiple}
        row.update(summarize_trades(trades))
        rows.append(row)

    summary = pd.DataFrame(rows).sort_values(["profit_factor", "avg_return"], ascending=[False, False]).reset_index(drop=True)
    return summary, trades_by_multiple
