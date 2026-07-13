from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.reversal_quality_score import score_reversal_quality
from src.data.validators import filter_primary_equity_symbols
from src.data.loaders import save_parquet
from src.utils.scoring import to_bool as _to_bool


ACTION_SCORE_MAP = {
    "Valid Breakout Setup": 100.0,
    "Watch - Limited Sample Breakout": 82.0,
    "Watch - Conditional Breakout": 70.0,
    "Watch - Need Confirmation": 60.0,
    "Watchlist - No Signal": 55.0,
    "Watchlist - Emerging": 50.0,
    "Watchlist - Conditional": 45.0,
    "No Signal": 20.0,
    "Avoid - Weak Historical Edge": 0.0,
    "Avoid - Bad Volatility Regime": 0.0,
}

VOLATILITY_RULE_SCORE_MAP = {
    "Allowed": 100.0,
    "Conditional": 65.0,
    "Ignore": 40.0,
    "Unknown": 50.0,
    "Avoid": 0.0,
}

REGIME_SCORE_MAP = {
    "Low Vol": 100.0,
    "Normal Vol": 78.0,
    "Stress Vol": 35.0,
    "Panic Vol": 5.0,
    "Unknown": 50.0,
}

def _clip_score(series: pd.Series, default: float = 50.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(default)
    return numeric.clip(lower=0.0, upper=100.0)


def _rank_score(series: pd.Series, higher_is_better: bool = True, default: float = 50.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series(default, index=series.index, dtype="float64")
    base = valid if higher_is_better else -valid
    ranked = base.rank(pct=True, method="average") * 100.0
    out = pd.Series(default, index=series.index, dtype="float64")
    out.loc[ranked.index] = ranked
    return out.clip(lower=0.0, upper=100.0)


def _latest_by_symbol(df: pd.DataFrame, symbol_col: str = "symbol", date_col: str = "date") -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col])
        out = out.sort_values([symbol_col, date_col]).groupby(symbol_col, as_index=False).tail(1)
    elif symbol_col in out.columns:
        out = out.drop_duplicates(subset=[symbol_col], keep="last")
    return out.reset_index(drop=True)


def _series_or_default(df: pd.DataFrame, column: str, default) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(default, index=df.index)


def _coalesce_series(*series_list: pd.Series) -> pd.Series:
    if not series_list:
        return pd.Series(dtype=float)
    out = series_list[0].copy()
    for series in series_list[1:]:
        out = out.where(out.notna(), series)
    return out


def _ensure_latest_feature_frame(
    features: pd.DataFrame,
    symbol_col: str = "symbol",
    date_col: str = "date",
    price_col: str = "close",
) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame(columns=[symbol_col, date_col, price_col])

    out = filter_primary_equity_symbols(features, symbol_col=symbol_col).copy()
    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col])
    if "return_20d" not in out.columns and price_col in out.columns:
        out = out.sort_values([symbol_col, date_col]).copy()
        out["return_20d"] = out.groupby(symbol_col)[price_col].pct_change(20)
    if "return_5d" not in out.columns and price_col in out.columns:
        out = out.sort_values([symbol_col, date_col]).copy()
        out["return_5d"] = out.groupby(symbol_col)[price_col].pct_change(5)
    if "above_ma20" not in out.columns and "ma20" in out.columns and price_col in out.columns:
        out["above_ma20"] = out[price_col] > out["ma20"]
    if "above_ma50" not in out.columns and "ma50" in out.columns and price_col in out.columns:
        out["above_ma50"] = out[price_col] > out["ma50"]
    if "above_ma200" not in out.columns and "ma200" in out.columns and price_col in out.columns:
        out["above_ma200"] = out[price_col] > out["ma200"]
    return _latest_by_symbol(out, symbol_col=symbol_col, date_col=date_col)


def _prepare_trade_card_frame(trade_cards: pd.DataFrame, symbol_col: str = "symbol", date_col: str = "date") -> pd.DataFrame:
    if trade_cards.empty:
        return pd.DataFrame(columns=[symbol_col, "trade_card_date"])
    out = _latest_by_symbol(filter_primary_equity_symbols(trade_cards, symbol_col=symbol_col), symbol_col=symbol_col, date_col=date_col)
    selected = [
        symbol_col,
        "date",
        "close",
        "breakout_20d",
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
    ]
    available = [col for col in selected if col in out.columns]
    rename_map = {
        "date": "trade_card_date",
        "close": "trade_card_close",
        "breakout_20d": "trade_breakout_20d",
        "volatility_regime": "trade_volatility_regime",
    }
    return out[available].rename(columns=rename_map)


def _prepare_stealth_frame(stealth: pd.DataFrame, symbol_col: str = "symbol", date_col: str = "date") -> pd.DataFrame:
    if stealth.empty:
        return pd.DataFrame(columns=[symbol_col, "stealth_date"])
    out = _latest_by_symbol(filter_primary_equity_symbols(stealth, symbol_col=symbol_col), symbol_col=symbol_col, date_col=date_col)
    selected = [
        symbol_col,
        "date",
        "close",
        "sector",
        "watchlist_flag",
        "net_accumulation_score",
        "accumulation_score",
        "breakout_quality_score",
        "relative_strength_score",
        "breadth_support_score",
        "sector_support_score",
        "market_support_score",
        "liquidity_score",
        "fakeout_risk_score",
        "overextension_risk_score",
        "upper_wick_risk_score",
        "volatility_spike_risk_score",
        "exhaustion_volume_risk_score",
        "tail_risk_score",
        "atr_pct_14",
        "avg_value_20d",
        "volatility_regime",
        "market_regime",
    ]
    available = [col for col in selected if col in out.columns]
    rename_map = {
        "date": "stealth_date",
        "close": "stealth_close",
        "sector": "stealth_sector",
        "atr_pct_14": "stealth_atr_pct_14",
        "avg_value_20d": "stealth_avg_value_20d",
        "volatility_regime": "stealth_volatility_regime",
    }
    return out[available].rename(columns=rename_map)


def prepare_meta_ranking_dataset(
    features: pd.DataFrame,
    trade_cards: pd.DataFrame | None = None,
    stealth: pd.DataFrame | None = None,
    signal_col: str = "breakout_20d",
) -> pd.DataFrame:
    trade_cards = trade_cards if trade_cards is not None else pd.DataFrame()
    stealth = stealth if stealth is not None else pd.DataFrame()

    latest_features = _ensure_latest_feature_frame(features)
    latest_trade = _prepare_trade_card_frame(trade_cards)
    latest_stealth = _prepare_stealth_frame(stealth)

    symbol_sets: list[set[str]] = []
    for frame in (latest_features, latest_trade, latest_stealth):
        if not frame.empty and "symbol" in frame.columns:
            symbol_sets.append(set(frame["symbol"].astype(str)))
    if not symbol_sets:
        return pd.DataFrame()

    universe = pd.DataFrame({"symbol": sorted(set().union(*symbol_sets))})
    merged = universe.merge(latest_features, on="symbol", how="left")
    merged = merged.merge(latest_trade, on="symbol", how="left")
    merged = merged.merge(latest_stealth, on="symbol", how="left")

    merged["date"] = pd.to_datetime(_series_or_default(merged, "date", pd.NaT))
    merged["trade_card_date"] = pd.to_datetime(_series_or_default(merged, "trade_card_date", pd.NaT))
    merged["stealth_date"] = pd.to_datetime(_series_or_default(merged, "stealth_date", pd.NaT))
    merged["analysis_date"] = _coalesce_series(merged["date"], merged["trade_card_date"], merged["stealth_date"])

    # G5: how many of the 3 signal sources (features/trade_card/stealth) actually
    # matched this symbol. A meta_score built mostly on default-50 filler must not
    # look as trustworthy as one backed by real evidence from all sources.
    has_features = merged["date"].notna()
    has_trade_card = merged["trade_card_date"].notna()
    has_stealth = merged["stealth_date"].notna()
    sources_present = has_features.astype(int) + has_trade_card.astype(int) + has_stealth.astype(int)
    merged["evidence_coverage"] = sources_present / 3.0
    merged["insufficient_evidence"] = sources_present <= 1

    # G3: the 3 sources are merged per-symbol without checking they refer to the
    # same trading day -- flag when they disagree by more than 3 calendar days.
    present_dates = pd.concat(
        [
            merged["date"].where(has_features),
            merged["trade_card_date"].where(has_trade_card),
            merged["stealth_date"].where(has_stealth),
        ],
        axis=1,
    )
    date_spread_days = (present_dates.max(axis=1) - present_dates.min(axis=1)).dt.days
    merged["source_date_spread_days"] = date_spread_days
    merged["signal_age_warning"] = date_spread_days.fillna(0) > 3
    merged["close"] = _coalesce_series(
        _series_or_default(merged, "close", np.nan),
        _series_or_default(merged, "trade_card_close", np.nan),
        _series_or_default(merged, "stealth_close", np.nan),
    )

    if "sector" not in merged.columns:
        merged["sector"] = np.nan
    merged["sector"] = merged["sector"].combine_first(_series_or_default(merged, "stealth_sector", np.nan))

    if "atr_pct_14" not in merged.columns:
        merged["atr_pct_14"] = np.nan
    merged["atr_pct_14"] = merged["atr_pct_14"].combine_first(_series_or_default(merged, "stealth_atr_pct_14", np.nan))

    if "avg_value_20d" not in merged.columns:
        merged["avg_value_20d"] = np.nan
    merged["avg_value_20d"] = merged["avg_value_20d"].combine_first(_series_or_default(merged, "stealth_avg_value_20d", np.nan))

    if signal_col not in merged.columns:
        merged[signal_col] = False
    merged[signal_col] = merged[signal_col].map(_to_bool)
    merged[signal_col] = merged[signal_col] | _series_or_default(merged, "trade_breakout_20d", False).map(_to_bool)

    if "eligible" not in merged.columns:
        merged["eligible"] = False
    merged["eligible"] = merged["eligible"].map(_to_bool)

    if "watchlist_eligible" not in merged.columns:
        merged["watchlist_eligible"] = False
    merged["watchlist_eligible"] = merged["watchlist_eligible"].map(_to_bool)

    if "watchlist_flag" not in merged.columns:
        merged["watchlist_flag"] = False
    merged["watchlist_flag"] = merged["watchlist_flag"].map(_to_bool)

    merged["volatility_regime"] = _series_or_default(merged, "trade_volatility_regime", np.nan).combine_first(
        _series_or_default(merged, "stealth_volatility_regime", np.nan)
    )
    merged["volatility_regime"] = merged["volatility_regime"].fillna("Unknown")
    merged["volatility_rule"] = _series_or_default(merged, "volatility_rule", "Unknown").fillna("Unknown")
    merged["action"] = _series_or_default(merged, "action", "No Signal").fillna("No Signal")
    merged["edge_tier"] = _series_or_default(merged, "edge_tier", "Unknown").fillna("Unknown")
    return merged


def score_meta_ranking(
    data: pd.DataFrame,
    signal_col: str = "breakout_20d",
) -> pd.DataFrame:
    if data.empty:
        return data.copy()

    ranked = data.copy()

    ranked["trade_edge_score"] = _clip_score(_series_or_default(ranked, "trade_edge_score", 0.0), default=0.0)
    ranked["setup_quality_score"] = _clip_score(_series_or_default(ranked, "setup_quality_score", 0.0), default=0.0)
    ranked["net_accumulation_score"] = _clip_score(
        _series_or_default(ranked, "net_accumulation_score", np.nan).combine_first(_series_or_default(ranked, "accumulation_score", 0.0)),
        default=0.0,
    )
    ranked["breakout_quality_score"] = _clip_score(_series_or_default(ranked, "breakout_quality_score", 0.0), default=0.0)
    ranked["relative_strength_score"] = _clip_score(_series_or_default(ranked, "relative_strength_score", np.nan))
    ranked["breadth_support_score"] = _clip_score(_series_or_default(ranked, "breadth_support_score", np.nan))
    ranked["sector_support_score"] = _clip_score(_series_or_default(ranked, "sector_support_score", np.nan))
    ranked["market_support_score"] = _clip_score(_series_or_default(ranked, "market_support_score", np.nan))
    ranked["liquidity_score"] = _clip_score(_series_or_default(ranked, "liquidity_score", np.nan))

    ranked["fakeout_risk_score"] = _clip_score(_series_or_default(ranked, "fakeout_risk_score", 35.0), default=35.0)
    ranked["overextension_risk_score"] = _clip_score(_series_or_default(ranked, "overextension_risk_score", 35.0), default=35.0)
    ranked["upper_wick_risk_score"] = _clip_score(_series_or_default(ranked, "upper_wick_risk_score", 30.0), default=30.0)
    ranked["volatility_spike_risk_score"] = _clip_score(_series_or_default(ranked, "volatility_spike_risk_score", 35.0), default=35.0)
    ranked["exhaustion_volume_risk_score"] = _clip_score(_series_or_default(ranked, "exhaustion_volume_risk_score", 30.0), default=30.0)
    ranked["tail_risk_score"] = _clip_score(_series_or_default(ranked, "tail_risk_score", 25.0), default=25.0)

    ranked["momentum_strength_score"] = _rank_score(_series_or_default(ranked, "return_20d", np.nan))
    ranked["short_term_momentum_score"] = _rank_score(_series_or_default(ranked, "return_5d", np.nan))
    ranked["volume_confirmation_score"] = _rank_score(_series_or_default(ranked, "volume_zscore_20d", np.nan))
    ranked["liquidity_rank_score"] = _rank_score(_series_or_default(ranked, "avg_value_20d", np.nan))
    ranked["atr_comfort_score"] = _rank_score(_series_or_default(ranked, "atr_pct_14", np.nan), higher_is_better=False)

    ranked["trend_alignment_score"] = (
        _series_or_default(ranked, "above_ma20", False).map(_to_bool).astype(float) * 34.0
        + _series_or_default(ranked, "above_ma50", False).map(_to_bool).astype(float) * 33.0
        + _series_or_default(ranked, "above_ma200", False).map(_to_bool).astype(float) * 33.0
    )

    ranked["action_score"] = ranked["action"].map(ACTION_SCORE_MAP).fillna(20.0)
    ranked["volatility_rule_score"] = ranked["volatility_rule"].map(VOLATILITY_RULE_SCORE_MAP).fillna(50.0)
    ranked["regime_score"] = ranked["volatility_regime"].map(REGIME_SCORE_MAP).fillna(50.0)

    ranked["breakout_component_score"] = (
        0.50 * ranked["trade_edge_score"]
        + 0.25 * ranked["setup_quality_score"]
        + 0.15 * ranked["volatility_rule_score"]
        + 0.10 * ranked["action_score"]
    ).clip(0.0, 100.0)

    ranked["stealth_component_score"] = (
        0.45 * ranked["net_accumulation_score"]
        + 0.20 * ranked["breakout_quality_score"]
        + 0.15 * ranked["relative_strength_score"]
        + 0.10 * ranked["breadth_support_score"]
        + 0.10 * ranked["sector_support_score"]
    ).clip(0.0, 100.0)

    ranked["momentum_component_score"] = (
        0.45 * ranked["momentum_strength_score"]
        + 0.15 * ranked["short_term_momentum_score"]
        + 0.20 * ranked["trend_alignment_score"]
        + 0.20 * ranked["volume_confirmation_score"]
    ).clip(0.0, 100.0)

    ranked["execution_component_score"] = (
        0.30 * ranked["liquidity_score"]
        + 0.25 * ranked["liquidity_rank_score"]
        + 0.20 * ranked["regime_score"]
        + 0.15 * ranked["atr_comfort_score"]
        + 0.10 * ranked["market_support_score"]
    ).clip(0.0, 100.0)

    ranked["risk_penalty_score"] = (
        0.35 * ranked["fakeout_risk_score"]
        + 0.20 * ranked["overextension_risk_score"]
        + 0.10 * ranked["upper_wick_risk_score"]
        + 0.15 * ranked["volatility_spike_risk_score"]
        + 0.10 * ranked["exhaustion_volume_risk_score"]
        + 0.10 * ranked["tail_risk_score"]
    ).clip(0.0, 100.0)

    # meta_score: walk-forward-validated mean-reversion 3-factor score (see
    # STRATEGY_RESEARCH_REPORT.md sections 3-6 and META_RANKING_VALIDATION_REPORT.md),
    # replacing the previous breakout/stealth/momentum/execution blend below --
    # that blend was validated (full formula, real trade_cards, walk-forward
    # reconstructed) to show NO alpha and a weak but significant NEGATIVE IC
    # (-0.079, t=-2.57), losing money in 3 of 5 independent rolling-fold years.
    # breakout_component_score/stealth_component_score/momentum_component_score/
    # execution_component_score/risk_penalty_score are kept below (unused for
    # meta_score itself now) purely as informational diagnostics for
    # meta_summary/setup_style and because final_watchlist.py still consumes
    # risk_penalty_score/trade_edge_score/setup_quality_score independently.
    factor_cols = [c for c in ("distance_ma20", "return_20d", "realized_vol_20d") if c in ranked.columns]
    reversal_input = ranked[["symbol", "date"] + factor_cols]
    reversal_scores = score_reversal_quality(reversal_input).set_index("symbol")["reversal_quality_score"]
    ranked["meta_score"] = ranked["symbol"].map(reversal_scores).fillna(50.0).clip(0.0, 100.0)

    ranked["meta_rank"] = ranked["meta_score"].rank(method="first", ascending=False).astype(int)
    ranked["setup_style"] = np.select(
        [
            (ranked["breakout_component_score"] >= 70) & (ranked["stealth_component_score"] >= 70),
            ranked["breakout_component_score"] >= 70,
            ranked["stealth_component_score"] >= 70,
            ranked["momentum_component_score"] >= 65,
        ],
        [
            "Hybrid Breakout + Accumulation",
            "Breakout-led",
            "Stealth Accumulation-led",
            "Momentum-led",
        ],
        default="Developing / Mixed",
    )
    ranked["priority_bucket"] = np.select(
        [
            (ranked["meta_score"] >= 75) & (ranked["risk_penalty_score"] <= 40),
            ranked["meta_score"] >= 60,
            ranked["meta_score"] >= 45,
        ],
        [
            "Prime Candidate",
            "High Conviction Watchlist",
            "Secondary Watchlist",
        ],
        default="Low Priority",
    )
    # G5: a symbol backed by <=1 of the 3 signal sources (mostly default-50 filler)
    # cannot be a Prime/High-Conviction candidate no matter how high meta_score reads.
    if "insufficient_evidence" in ranked.columns:
        thin_evidence = ranked["insufficient_evidence"].fillna(False)
        capped = thin_evidence & ranked["priority_bucket"].isin(["Prime Candidate", "High Conviction Watchlist"])
        ranked.loc[capped, "priority_bucket"] = "Secondary Watchlist"
    ranked["meta_summary"] = ranked.apply(describe_meta_signal, axis=1, signal_col=signal_col)
    return ranked.sort_values(["meta_score", "trade_edge_score", "net_accumulation_score"], ascending=False).reset_index(drop=True)


def describe_meta_signal(row: pd.Series, signal_col: str = "breakout_20d") -> str:
    symbol = row.get("symbol", "Unknown")
    meta_score = float(row.get("meta_score", 0.0))
    style = row.get("setup_style", "Developing / Mixed")
    vol_regime = row.get("volatility_regime", "Unknown")
    breakout_live = _to_bool(row.get(signal_col, False))
    stealth_live = _to_bool(row.get("watchlist_flag", False))
    risk = float(row.get("risk_penalty_score", 50.0))

    catalysts = []
    if breakout_live:
        catalysts.append("breakout đang active")
    if stealth_live:
        catalysts.append("stealth accumulation đang hợp lệ")
    if float(row.get("momentum_component_score", 0.0)) >= 65:
        catalysts.append("momentum đang tốt")
    catalyst_text = ", ".join(catalysts) if catalysts else "chưa có catalyst quá mạnh"

    return (
        f"{symbol}: meta score {meta_score:.1f}/100, phong cách {style}, regime {vol_regime}. "
        f"Điểm nhấn: {catalyst_text}. Risk penalty khoảng {risk:.1f}/100."
    )


def build_meta_ranking(
    features: pd.DataFrame,
    trade_cards: pd.DataFrame | None = None,
    stealth: pd.DataFrame | None = None,
    signal_col: str = "breakout_20d",
) -> pd.DataFrame:
    prepared = prepare_meta_ranking_dataset(
        features=features,
        trade_cards=trade_cards,
        stealth=stealth,
        signal_col=signal_col,
    )
    return score_meta_ranking(prepared, signal_col=signal_col)


def merge_alpha_score_v2(ranked: pd.DataFrame, alpha_scores: pd.DataFrame) -> pd.DataFrame:
    """Merge only the validated v2 alpha_score into the meta-ranking dataset.

    Does NOT merge any v1 shadow per-component score (momentum_score,
    rs_score, trend_score, volume_score, volatility_score, liquidity_score).
    SCORE_FORENSIC_REPORT.md found the v1 composite had no significant
    standalone IC anywhere tested, and specifically that rs_score's IC
    flipped to -0.1060 in 2026 (a primary driver of a real -59.7% backtest
    loss). This function previously merged all 6 v1 fields in as
    alpha_momentum_score/alpha_rs_score/alpha_trend_score/alpha_volume_score/
    alpha_volatility_score/alpha_liquidity_score with zero downstream
    consumer (save_meta_ranking_outputs applies no column restriction, so
    they rode straight into the saved data/signals/meta_ranking*.parquet
    report files) -- pure leakage, removed (audit gate #17). v1's
    components remain available for shadow comparison only in
    data/signals/alpha_scores.parquet and
    data/signals/alpha_score_shadow_log.parquet -- never here.
    """
    if alpha_scores is None or alpha_scores.empty or ranked.empty:
        return ranked
    alpha_latest = alpha_scores.sort_values("date").groupby("symbol").tail(1)
    keep = [c for c in ["symbol", "alpha_score"] if c in alpha_latest.columns]
    if len(keep) <= 1:
        return ranked
    return ranked.merge(alpha_latest[keep], on="symbol", how="left")


def top_meta_candidates(
    ranked: pd.DataFrame,
    top_n: int = 20,
    min_score: float = 50.0,
    allowed_buckets: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if ranked.empty:
        return ranked.copy()
    allowed_buckets = allowed_buckets or ("Prime Candidate", "High Conviction Watchlist", "Secondary Watchlist")
    out = ranked[ranked["meta_score"] >= min_score].copy()
    out = out[out["priority_bucket"].isin(allowed_buckets)]
    return out.head(top_n).reset_index(drop=True)


def save_meta_ranking_outputs(
    ranked: pd.DataFrame,
    out_dir: str = "data/signals",
    prefix: str = "meta_ranking",
    top_n: int = 20,
    min_score: float = 50.0,
) -> dict[str, Path]:
    from src.validation.guards import assert_no_forward_columns

    out_dir_path = Path(out_dir)
    latest_path = out_dir_path / f"{prefix}.parquet"
    top_path = out_dir_path / f"{prefix}_watchlist.parquet"
    prime_path = out_dir_path / f"{prefix}_prime.parquet"

    # D5: forward_/future_ columns are backtest-only labels; they must not ride
    # into a live-scoring output artifact.
    ranked = assert_no_forward_columns(ranked, context="meta_ranking.save_meta_ranking_outputs", mode="drop")

    save_parquet(ranked, latest_path)
    save_parquet(top_meta_candidates(ranked, top_n=top_n, min_score=min_score), top_path)
    save_parquet(top_meta_candidates(ranked, top_n=top_n, min_score=75.0, allowed_buckets=("Prime Candidate",)), prime_path)
    return {
        "ranked": latest_path,
        "watchlist": top_path,
        "prime": prime_path,
    }
