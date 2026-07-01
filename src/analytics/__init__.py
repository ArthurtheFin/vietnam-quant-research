from src.analytics.correlation import (
    build_return_matrix,
    compute_correlation_matrix,
    rolling_pair_correlation,
    top_correlation_pairs,
)
from src.analytics.benchmark import (
    build_market_proxy_benchmark,
    compare_benchmark_to_proxy,
    load_processed_benchmark,
    summarize_benchmark_alignment,
)
from src.analytics.advanced import (
    add_cross_sectional_momentum_rank,
    compute_rolling_beta,
    correlation_matrix_by_regime,
    correlations_by_regime,
    pair_divergence_zscore,
    screen_pair_divergences,
)
from src.analytics.entropy import (
    add_entropy_features,
    build_market_entropy_profile,
    classify_entropy_regime,
    detect_entropy_regime_shift,
    rolling_shannon_entropy,
)
from src.analytics.meta_ranking import (
    build_meta_ranking,
    describe_meta_signal,
    prepare_meta_ranking_dataset,
    save_meta_ranking_outputs,
    score_meta_ranking,
    top_meta_candidates,
)
from src.analytics.sector_board import (
    attach_sector,
    audit_sector_mapping,
    build_sector_board,
    build_sector_leaders,
    compute_sector_metrics,
    ensure_sector_map_template,
    load_sector_board_inputs,
    load_sector_map,
    normalize_sector_map,
    rank_sectors,
    write_sector_outputs,
)
