from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from risk import max_drawdown, ratios, rolling_capm, var_cvar


def enrich(stock: pd.DataFrame, benchmark: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    s = _technical(stock.copy(), int(cfg.get("atr_period", 14)))
    b = _technical(benchmark.copy(), int(cfg.get("atr_period", 14)))
    s, b, rs = _relative_strength(s, b)
    aligned = _aligned_returns(s, b)
    perf = ratios(aligned["stock"], aligned["bench"], float(cfg.get("risk_free_rate_annual", 0.0)), int(cfg.get("trading_days", 252)))
    roll = rolling_capm(aligned["stock"], aligned["bench"], 60, int(cfg.get("trading_days", 252)))
    metrics = _latest_metrics(s, b, rs, perf, cfg)
    return s, b, rs, roll, metrics


def _technical(df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    out = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for w in [5, 20, 50, 60, 100, 120, 200]:
        out[f"ma{w}"] = out["close"].rolling(w, min_periods=max(3, w // 4)).mean()
        out[f"return_{w}d"] = out["close"].pct_change(w)
    out["ret"] = out["close"].pct_change()
    out["log_ret"] = np.log(out["close"]).diff()
    out["ma20_slope"] = out["ma20"].pct_change(10)
    out["ma50_slope"] = out["ma50"].pct_change(20)
    out["ma50_slope_bars"] = out["ma50"].diff(20)
    out["distance_ma20"] = out["close"] / out["ma20"] - 1.0
    out["distance_ma50"] = out["close"] / out["ma50"] - 1.0
    out["distance_ma200"] = out["close"] / out["ma200"] - 1.0
    prev = out["close"].shift(1)
    tr = pd.concat([(out["high"] - out["low"]).abs(), (out["high"] - prev).abs(), (out["low"] - prev).abs()], axis=1).max(axis=1)
    out["true_range"] = tr
    out["atr"] = tr.rolling(atr_period, min_periods=max(3, atr_period // 2)).mean()
    out["atr_pct"] = out["atr"] / out["close"]
    out["vol_20d"] = out["ret"].rolling(20, min_periods=10).std() * np.sqrt(252)
    out["vol_60d"] = out["ret"].rolling(60, min_periods=20).std() * np.sqrt(252)
    out["ewma_vol"] = out["ret"].ewm(span=20, min_periods=10).std() * np.sqrt(252)
    out["volatility_percentile"] = out["vol_20d"].rolling(252, min_periods=60).rank(pct=True) * 100
    out["drawdown"] = max_drawdown(out["close"])
    out["max_drawdown"] = out["drawdown"].rolling(252, min_periods=60).min()
    out["roc_20d"] = out["close"].pct_change(20)
    out["roc_60d"] = out["close"].pct_change(60)
    out["rsi_14"] = _rsi(out["close"], 14)
    out["macd"], out["macd_signal"], out["macd_hist"] = _macd(out["close"])
    out["momentum_acceleration"] = out["return_20d"] - out["return_60d"]
    out["week_52_high_distance"] = out["close"] / out["close"].rolling(252, min_periods=60).max() - 1.0
    out["donchian_20_breakout"] = out["close"] >= out["high"].rolling(20, min_periods=10).max().shift(1)
    out["donchian_55_breakout"] = out["close"] >= out["high"].rolling(55, min_periods=20).max().shift(1)
    out["adx"], out["plus_di"], out["minus_di"] = _adx(out, 14)
    _volume_features(out)
    return out


def _volume_features(out: pd.DataFrame) -> None:
    out["trading_value"] = out.get("value", out["close"] * out["volume"])
    out["avg_volume_20d"] = out["volume"].rolling(20, min_periods=5).mean()
    out["avg_volume_60d"] = out["volume"].rolling(60, min_periods=10).mean()
    out["avg_value_20d"] = out["trading_value"].rolling(20, min_periods=5).mean()
    out["volume_ratio"] = out["volume"] / out["avg_volume_20d"].replace(0, np.nan)
    out["volume_zscore"] = (out["volume"] - out["avg_volume_20d"]) / out["volume"].rolling(20, min_periods=5).std().replace(0, np.nan)
    direction = np.sign(out["close"].diff()).fillna(0.0)
    out["obv"] = (direction * out["volume"]).cumsum()
    tp = (out["high"] + out["low"] + out["close"]) / 3.0
    mf = tp * out["volume"]
    pos = mf.where(tp.diff() > 0, 0.0).rolling(14, min_periods=5).sum()
    neg = mf.where(tp.diff() < 0, 0.0).rolling(14, min_periods=5).sum().abs()
    out["mfi"] = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    denom = (out["high"] - out["low"]).replace(0, np.nan)
    mf_mult = ((out["close"] - out["low"]) - (out["high"] - out["close"])) / denom
    out["adl"] = (mf_mult.fillna(0.0) * out["volume"]).cumsum()
    out["cmf"] = (mf_mult.fillna(0.0) * out["volume"]).rolling(20, min_periods=5).sum() / out["volume"].rolling(20, min_periods=5).sum().replace(0, np.nan)


def _relative_strength(s: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    left = s.set_index("date")
    right = b.set_index("date")
    aligned = pd.concat([left["close"], right["close"]], axis=1, keys=["stock", "bench"]).dropna()
    stock_cum = aligned["stock"] / aligned["stock"].iloc[0] - 1.0
    bench_cum = aligned["bench"] / aligned["bench"].iloc[0] - 1.0
    rs_line = aligned["stock"] / aligned["bench"]
    rs = pd.DataFrame(
        {
            "date": aligned.index,
            "stock_cum_return": stock_cum.values,
            "benchmark_cum_return": bench_cum.values,
            "relative_strength_line": rs_line.values,
            "rs_slope": rs_line.pct_change(20).values,
            "excess_return_20d": (aligned["stock"].pct_change(20) - aligned["bench"].pct_change(20)).values,
            "excess_return_60d": (aligned["stock"].pct_change(60) - aligned["bench"].pct_change(60)).values,
            "rolling_corr": aligned["stock"].pct_change().rolling(60, min_periods=20).corr(aligned["bench"].pct_change()).values,
            "rolling_beta": (aligned["stock"].pct_change().rolling(60, min_periods=20).cov(aligned["bench"].pct_change()) / aligned["bench"].pct_change().rolling(60, min_periods=20).var()).values,
        }
    )
    s = s.merge(rs[["date", "excess_return_20d", "excess_return_60d", "relative_strength_line", "rs_slope", "rolling_corr", "rolling_beta"]], on="date", how="left")
    return s, b, rs


def _latest_metrics(s: pd.DataFrame, b: pd.DataFrame, rs: pd.DataFrame, perf: dict[str, float], cfg: dict[str, Any]) -> dict[str, Any]:
    row = s.dropna(subset=["close"]).iloc[-1]
    brow = b.dropna(subset=["close"]).iloc[-1]
    rr = _entry_metrics(row, cfg)
    returns = s["ret"].dropna()
    var95, cvar95 = var_cvar(returns, 0.95)
    market_recent_high = b["close"].tail(120).max()
    metrics: dict[str, Any] = {
        "date": row["date"],
        "close": float(row["close"]),
        "market_close": float(brow["close"]),
        "market_above_ma20": bool(brow["close"] > brow.get("ma20", np.nan)),
        "market_above_ma50": bool(brow["close"] > brow.get("ma50", np.nan)),
        "market_above_ma200": bool(brow["close"] > brow.get("ma200", np.nan)),
        "market_ma50_slope": _f(brow.get("ma50_slope")),
        "market_return_20d": _f(brow.get("return_20d")),
        "market_return_60d": _f(brow.get("return_60d")),
        "market_volatility_percentile": _f(brow.get("volatility_percentile")),
        "market_drawdown": _f(brow["close"] / market_recent_high - 1.0),
        "above_ma20": bool(row["close"] > row.get("ma20", np.nan)),
        "above_ma50": bool(row["close"] > row.get("ma50", np.nan)),
        "above_ma100": bool(row["close"] > row.get("ma100", np.nan)),
        "above_ma200": bool(row["close"] > row.get("ma200", np.nan)),
        "ma_stack": bool(row.get("ma20", 0) > row.get("ma50", np.inf) > row.get("ma200", np.inf)),
        "ma20_slope": _f(row.get("ma20_slope")),
        "ma50_slope": _f(row.get("ma50_slope")),
        "distance_ma20": _f(row.get("distance_ma20")),
        "distance_ma50": _f(row.get("distance_ma50")),
        "week_52_high_distance": _f(row.get("week_52_high_distance")),
        "donchian_20_breakout": bool(row.get("donchian_20_breakout", False)),
        "donchian_55_breakout": bool(row.get("donchian_55_breakout", False)),
        "adx": _f(row.get("adx")),
        "plus_di": _f(row.get("plus_di")),
        "minus_di": _f(row.get("minus_di")),
        "rsi_14": _f(row.get("rsi_14")),
        "macd": _f(row.get("macd")),
        "macd_signal": _f(row.get("macd_signal")),
        "macd_hist": _f(row.get("macd_hist")),
        "momentum_acceleration": _f(row.get("momentum_acceleration")),
        "return_5d": _f(row.get("return_5d")),
        "return_20d": _f(row.get("return_20d")),
        "return_60d": _f(row.get("return_60d")),
        "return_120d": _f(row.get("return_120d")),
        "excess_return_20d": _f(row.get("excess_return_20d")),
        "excess_return_60d": _f(row.get("excess_return_60d")),
        "rs_slope": _f(row.get("rs_slope")),
        "rolling_corr": _f(row.get("rolling_corr")),
        "rolling_beta": _f(row.get("rolling_beta")),
        "atr": _f(row.get("atr")),
        "atr_pct": _f(row.get("atr_pct")),
        "vol_20d": _f(row.get("vol_20d")),
        "vol_60d": _f(row.get("vol_60d")),
        "ewma_vol": _f(row.get("ewma_vol")),
        "volatility_percentile": _f(row.get("volatility_percentile")),
        "max_drawdown": _f(s["drawdown"].min()),
        "downside_deviation": float(returns[returns < 0].std(ddof=1) * np.sqrt(252)) if len(returns[returns < 0]) else 0.0,
        "var_95": _f(var95),
        "cvar_95": _f(cvar95),
        "skewness": _f(returns.skew()),
        "kurtosis": _f(returns.kurt()),
        "avg_volume_20d": _f(row.get("avg_volume_20d")),
        "avg_volume_60d": _f(row.get("avg_volume_60d")),
        "avg_value_20d": _f(row.get("avg_value_20d")),
        "volume_ratio": _f(row.get("volume_ratio")),
        "volume_zscore": _f(row.get("volume_zscore")),
        "mfi": _f(row.get("mfi")),
        "cmf": _f(row.get("cmf")),
    }
    metrics.update(perf)
    metrics.update(rr)
    metrics["relative_strength_latest"] = rs.tail(1).to_dict("records")[0] if not rs.empty else {}
    return metrics


def _entry_metrics(row: pd.Series, cfg: dict[str, Any]) -> dict[str, float | str | bool]:
    close = float(row["close"])
    atr = _f(row.get("atr"))
    buffer = float(cfg.get("entry_atr_buffer", 0.5))
    stop_mult = float(cfg.get("stop_atr_multiplier", 2.0))
    t1_mult = float(cfg.get("target_atr_multiplier_1", 3.0))
    t2_mult = float(cfg.get("target_atr_multiplier_2", 5.0))
    entry_low = max(close - buffer * atr, 0.0)
    entry_high = close + 0.25 * buffer * atr
    stop = close - stop_mult * atr
    target1 = close + t1_mult * atr
    target2 = close + t2_mult * atr
    risk = close - stop
    rr = (target1 - close) / risk if risk > 0 else np.nan
    extension = _f(row.get("distance_ma20"))
    bad_extension = extension > max(0.08, 2.0 * _f(row.get("atr_pct")))
    pullback = abs(extension) <= max(0.03, _f(row.get("atr_pct")) * 1.2)
    return {
        "entry_zone_low": entry_low,
        "entry_zone_high": entry_high,
        "stop_loss": stop,
        "target_1": target1,
        "target_2": target2,
        "risk_reward": rr,
        "stop_distance_pct": risk / close if close else np.nan,
        "price_extension_warning": bool(bad_extension),
        "breakout_confirmation": bool(row.get("donchian_20_breakout", False) and row.get("volume_ratio", 0) >= 1.1),
        "pullback_quality": "Good" if pullback and close > row.get("ma50", np.inf) else "Poor" if bad_extension else "Neutral",
    }


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n, min_periods=max(5, n // 2)).mean()
    loss = (-delta.clip(upper=0)).rolling(n, min_periods=max(5, n // 2)).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = line.ewm(span=9, adjust=False).mean()
    return line, signal, line - signal


def _adx(df: pd.DataFrame, n: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    trn = df["true_range"].rolling(n, min_periods=max(5, n // 2)).sum().replace(0, np.nan)
    plus_di = 100 * plus_dm.rolling(n, min_periods=max(5, n // 2)).sum() / trn
    minus_di = 100 * minus_dm.rolling(n, min_periods=max(5, n // 2)).sum() / trn
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.rolling(n, min_periods=max(5, n // 2)).mean(), plus_di, minus_di


def _aligned_returns(s: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([s.set_index("date")["ret"], b.set_index("date")["ret"]], axis=1, keys=["stock", "bench"]).dropna()


def _f(x: Any, default: float = 0.0) -> float:
    try:
        out = float(x)
    except (TypeError, ValueError):
        return default
    return default if not np.isfinite(out) else out
