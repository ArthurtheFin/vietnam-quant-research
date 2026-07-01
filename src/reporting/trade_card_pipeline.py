from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.validators import filter_primary_equity_symbols
from src.data.loaders import save_parquet
from src.utils.scoring import to_bool as _to_bool


def _ensure_feature_columns(data: pd.DataFrame, signal_col: str) -> pd.DataFrame:
    out = filter_primary_equity_symbols(data).copy()
    if "date" not in out.columns:
        raise KeyError("features must contain a 'date' column")
    if "symbol" not in out.columns:
        raise KeyError("features must contain a 'symbol' column")
    if "close" not in out.columns:
        raise KeyError("features must contain a 'close' column")
    if signal_col not in out.columns:
        out[signal_col] = False
    if "volatility_regime" not in out.columns:
        out["volatility_regime"] = "Unknown"
    return out


def _normalize_eligibility(eligibility: pd.DataFrame) -> pd.DataFrame:
    required = [
        "symbol",
        "setup_name",
        "edge_tier",
        "eligible",
        "watchlist_eligible",
        "profit_factor",
        "avg_return",
        "median_return",
        "stop_loss",
        "holding_period",
        "cost_assumption",
    ]
    out = eligibility.copy()
    if "symbol" not in out.columns and out.index.name == "symbol":
        out = out.reset_index()
    defaults = {
        "symbol": pd.Series(dtype="object"),
        "setup_name": "breakout_20d",
        "edge_tier": "Insufficient Data",
        "eligible": False,
        "watchlist_eligible": False,
        "profit_factor": np.nan,
        "avg_return": np.nan,
        "median_return": np.nan,
        "stop_loss": np.nan,
        "holding_period": np.nan,
        "cost_assumption": np.nan,
    }
    for col in required:
        if col not in out.columns:
            out[col] = defaults.get(col, np.nan)
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    out["edge_tier"] = out["edge_tier"].fillna("Insufficient Data").astype(str)
    out["eligible"] = out["eligible"].fillna(False).map(_to_bool)
    out["watchlist_eligible"] = out["watchlist_eligible"].fillna(False).map(_to_bool)
    return out[required].copy()


def _normalize_vol_rule(vol_rule: pd.DataFrame) -> pd.DataFrame:
    out = vol_rule.copy()
    if "volatility_regime" not in out.columns and out.index.name == "volatility_regime":
        out = out.reset_index()
    if "volatility_regime" not in out.columns:
        out["volatility_regime"] = pd.Series(dtype="object")
    if "volatility_rule" not in out.columns:
        out["volatility_rule"] = pd.Series(dtype="object")
    return out[["volatility_regime", "volatility_rule"]].copy()


def _fill_missing_trade_card_fields(trade_cards: pd.DataFrame) -> pd.DataFrame:
    out = trade_cards.copy()
    defaults = {
        "edge_tier": "Insufficient Data",
        "eligible": False,
        "watchlist_eligible": False,
        "profit_factor": np.nan,
        "avg_return": np.nan,
        "median_return": np.nan,
        "stop_loss": np.nan,
        "holding_period": np.nan,
        "cost_assumption": np.nan,
        "volatility_rule": "Unknown",
    }
    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default
    out["edge_tier"] = out["edge_tier"].fillna("Insufficient Data").astype(str)
    out["eligible"] = out["eligible"].map(lambda value: False if pd.isna(value) else _to_bool(value)).astype(bool)
    out["watchlist_eligible"] = out["watchlist_eligible"].map(lambda value: False if pd.isna(value) else _to_bool(value)).astype(bool)
    out["volatility_rule"] = out["volatility_rule"].fillna("Unknown").astype(str)
    return out


def decide_action(row: pd.Series, signal_col: str = "breakout_20d") -> str:
    signal = _to_bool(row.get(signal_col, False))
    eligible = _to_bool(row.get("eligible", False))
    watchlist_eligible_val = row.get("watchlist_eligible")
    if pd.isna(watchlist_eligible_val):
        watchlist_eligible = eligible
    else:
        watchlist_eligible = _to_bool(watchlist_eligible_val)
    vol_rule_value = row.get("volatility_rule", "Unknown")
    edge_tier = str(row.get("edge_tier", "Unknown") or "Unknown")

    if not signal:
        if eligible and vol_rule_value == "Allowed":
            return "Watchlist - No Signal"
        if watchlist_eligible and edge_tier == "Emerging Edge" and vol_rule_value in {"Allowed", "Conditional"}:
            return "Watchlist - Emerging"
        if watchlist_eligible and vol_rule_value in {"Allowed", "Conditional"}:
            return "Watchlist - Conditional"
        return "No Signal"

    # For active signals:
    if edge_tier == "Avoid":
        return "Avoid - Weak Historical Edge"
    if vol_rule_value == "Avoid":
        return "Avoid - Bad Volatility Regime"

    if eligible and vol_rule_value == "Allowed":
        return "Valid Breakout Setup"
    if edge_tier == "Emerging Edge" and vol_rule_value == "Allowed":
        return "Watch - Limited Sample Breakout"
    if vol_rule_value == "Conditional" or edge_tier == "Conditional Edge":
        return "Watch - Conditional Breakout"

    # If the edge tier is Insufficient Data or Unknown:
    if edge_tier in {"Insufficient Data", "Unknown", "nan"} or pd.isna(row.get("edge_tier")):
        if vol_rule_value == "Allowed":
            return "Watch - No Historical Edge Info"
        if vol_rule_value == "Conditional":
            return "Watch - Conditional Breakout"
        return "Watch - Need Confirmation"

    return "Watch - Need Confirmation"


def setup_quality_score(row: pd.Series) -> int:
    score = 0
    edge_tier = row.get("edge_tier", "")
    if edge_tier == "Strong Edge":
        score += 40
    elif edge_tier == "Valid Edge":
        score += 30
    elif edge_tier == "Emerging Edge":
        score += 22
    elif edge_tier == "Conditional Edge":
        score += 15

    vol_rule_value = row.get("volatility_rule", "")
    if vol_rule_value == "Allowed":
        score += 30
    elif vol_rule_value == "Conditional":
        score += 15
    elif vol_rule_value == "Ignore":
        score += 5

    if _to_bool(row.get("above_ma20", False)):
        score += 7
    if _to_bool(row.get("above_ma50", False)):
        score += 7
    if _to_bool(row.get("above_ma200", False)):
        score += 6
    if row.get("volume_zscore_20d", 0) > 1:
        score += 10
    return min(score, 100)


def trade_edge_score(row: pd.Series, signal_col: str = "breakout_20d") -> int:
    signal = _to_bool(row.get(signal_col, False))
    if not signal:
        return 0

    action = row.get("action", "")
    if action == "Valid Breakout Setup":
        return min(int(row["setup_quality_score"]) + 20, 100)
    if action == "Watch - Limited Sample Breakout":
        return min(int(row["setup_quality_score"]), 70)
    if action == "Watch - Conditional Breakout":
        return min(int(row["setup_quality_score"]), 75)
    if action == "Watch - No Historical Edge Info":
        return min(int(row["setup_quality_score"]), 65)
    return 0


def data_is_saying(row: pd.Series, signal_col: str = "breakout_20d") -> str:
    symbol = row["symbol"]
    signal = _to_bool(row.get(signal_col, False))
    action = row["action"]
    edge_tier = row.get("edge_tier", "Unknown")
    vol_regime = row.get("volatility_regime", "Unknown")
    vol_rule_value = row.get("volatility_rule", "Unknown")
    pf = row.get("profit_factor", np.nan)
    eligible = _to_bool(row.get("eligible", False))
    watchlist_eligible = _to_bool(row.get("watchlist_eligible", eligible))

    if not signal:
        if eligible and vol_rule_value == "Allowed":
            return (
                f"{symbol}: chưa có breakout 20D mới, nhưng mã này nằm trong nhóm có edge lịch sử "
                f"và volatility regime hiện tại đang cho phép. Đưa vào watchlist, chờ tín hiệu breakout."
            )
        if watchlist_eligible and edge_tier == "Emerging Edge":
            return (
                f"{symbol}: thống kê breakout trên mã này còn ít mẫu nhưng chất lượng gần đây khá tốt. "
                f"Đưa vào watchlist ưu tiên theo dõi, chưa xem là tín hiệu trade xác nhận."
            )
        if watchlist_eligible and vol_rule_value != "Avoid":
            return (
                f"{symbol}: chưa có breakout 20D mới. Mã có edge ở mức theo dõi và volatility regime hiện là "
                f"{vol_regime}. Theo dõi tiếp, chưa hành động."
            )
        return f"{symbol}: chưa có breakout 20D mới và edge lịch sử chưa đủ mạnh. Không ưu tiên cho setup này."

    if action == "Valid Breakout Setup":
        return (
            f"{symbol}: có breakout 20D hợp lệ. Historical edge: {edge_tier}, "
            f"profit factor khoảng {pf:.2f}, volatility regime: {vol_regime}. "
            f"Setup đủ điều kiện vào watchlist giao dịch. Stop-loss mặc định: -10%, holding max: 20 phiên."
        )
    if action == "Watch - Limited Sample Breakout":
        return (
            f"{symbol}: có breakout 20D nhưng mẫu thống kê lịch sử còn mỏng. "
            f"Có thể theo dõi sát và chờ thêm xác nhận thay vì vào lệnh mạnh tay ngay."
        )
    if "Weak Historical Edge" in action:
        return f"{symbol}: có breakout 20D nhưng lịch sử setup trên mã này yếu. Không nên mua chỉ vì giá vượt đỉnh."
    if "Bad Volatility" in action:
        return f"{symbol}: có breakout 20D nhưng volatility regime hiện tại là {vol_regime}, không ủng hộ breakout. Ưu tiên bỏ qua."
    return f"{symbol}: có tín hiệu breakout nhưng điều kiện chưa hoàn toàn xác nhận. Edge tier: {edge_tier}, volatility rule: {vol_rule_value}."


def build_trade_cards(
    features: pd.DataFrame,
    eligibility: pd.DataFrame,
    vol_rule: pd.DataFrame,
    signal_col: str = "breakout_20d",
    latest_only: bool = True,
) -> pd.DataFrame:
    data = _ensure_feature_columns(features, signal_col=signal_col)
    data["date"] = pd.to_datetime(data["date"])
    eligibility_norm = _normalize_eligibility(eligibility)
    vol_rule_norm = _normalize_vol_rule(vol_rule)

    if latest_only:
        data = data.sort_values(["symbol", "date"]).groupby("symbol").tail(1).copy()

    trade_cards = data.merge(
        eligibility_norm,
        on="symbol",
        how="left",
    )
    trade_cards = trade_cards.merge(
        vol_rule_norm,
        on="volatility_regime",
        how="left",
    )
    trade_cards = _fill_missing_trade_card_fields(trade_cards)

    trade_cards["action"] = trade_cards.apply(decide_action, axis=1, signal_col=signal_col)
    trade_cards["setup_quality_score"] = trade_cards.apply(setup_quality_score, axis=1)
    trade_cards["trade_edge_score"] = trade_cards.apply(trade_edge_score, axis=1, signal_col=signal_col)
    trade_cards["data_is_saying"] = trade_cards.apply(data_is_saying, axis=1, signal_col=signal_col)

    final_cols = [
        "symbol",
        "date",
        "close",
        signal_col,
        "edge_tier",
        "eligible",
        "watchlist_eligible",
        "volatility_regime",
        "volatility_rule",
        "profit_factor",
        "avg_return",
        "median_return",
        "stop_loss",
        "holding_period",
        "setup_quality_score",
        "trade_edge_score",
        "action",
        "data_is_saying",
    ]
    return trade_cards[final_cols].sort_values(
        ["trade_edge_score", "setup_quality_score", "profit_factor"],
        ascending=False,
    ).reset_index(drop=True)


def build_daily_watchlist(trade_cards: pd.DataFrame, signal_col: str = "breakout_20d", top_n: int = 10) -> pd.DataFrame:
    cols = [
        "symbol",
        "date",
        "close",
        signal_col,
        "edge_tier",
        "volatility_regime",
        "volatility_rule",
        "setup_quality_score",
        "trade_edge_score",
        "action",
    ]
    action_priority_map = {
        "Valid Breakout Setup": 10,
        "Watch - Limited Sample Breakout": 9,
        "Watch - Conditional Breakout": 8,
        "Watch - No Historical Edge Info": 7,
        "Watch - Need Confirmation": 6,
        "Watchlist - No Signal": 3,
        "Watchlist - Emerging": 2,
        "Watchlist - Conditional": 1,
        "No Signal": 0,
        "Avoid - Weak Historical Edge": -1,
        "Avoid - Bad Volatility Regime": -2,
    }

    data = trade_cards.copy()
    if not data.empty:
        latest_date = data["date"].max()
        data = data[data["date"] == latest_date].copy()

    data["action_priority"] = data.get("action", "No Signal").map(action_priority_map).fillna(0)
    preferred = data[data["action_priority"] > 0].copy()
    if preferred.empty:
        preferred = data.copy()

    sort_cols = [col for col in ["action_priority", "trade_edge_score", "setup_quality_score", "profit_factor"] if col in preferred.columns]
    sorted_df = preferred.sort_values(
        sort_cols,
        ascending=False,
    )
    return sorted_df[cols].head(top_n).reset_index(drop=True)


def save_trade_cards(trade_cards: pd.DataFrame, path: str = "data/signals/breakout_20d_trade_cards.parquet") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out = trade_cards.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str)
    save_parquet(out, path)
