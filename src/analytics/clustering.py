"""Hierarchical clustering for stock correlation matrices."""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform


def correlation_distance_matrix(corr_matrix: pd.DataFrame) -> pd.DataFrame:
    """Calculate distance matrix from correlation matrix: d = sqrt(0.5 * (1 - r))."""
    r = corr_matrix.clip(-1.0, 1.0)
    dist = np.sqrt(0.5 * (1.0 - r))
    np.fill_diagonal(dist.values, 0.0)
    return dist


def hierarchical_cluster_symbols(
    corr_matrix: pd.DataFrame,
    method: str = "ward",
) -> np.ndarray:
    """Perform hierarchical clustering on symbols using correlation distance."""
    dist_df = correlation_distance_matrix(corr_matrix)
    condensed = squareform(dist_df.to_numpy(), checks=False)
    Z = linkage(condensed, method=method)
    return Z


def get_cluster_labels(
    corr_matrix: pd.DataFrame,
    n_clusters: int = 5,
    method: str = "ward",
) -> pd.Series:
    """Assign cluster labels to symbols."""
    from scipy.cluster.hierarchy import cut_tree
    Z = hierarchical_cluster_symbols(corr_matrix, method=method)
    labels = cut_tree(Z, n_clusters=n_clusters).flatten()
    return pd.Series(labels, index=corr_matrix.index, name="cluster")


def order_correlation_matrix_by_cluster(
    corr_matrix: pd.DataFrame,
    method: str = "ward",
) -> pd.DataFrame:
    """Reorder a correlation matrix so clustered assets are adjacent."""
    if corr_matrix.empty or len(corr_matrix.index) <= 1:
        return corr_matrix
        
    Z = hierarchical_cluster_symbols(corr_matrix, method=method)
    leaves = leaves_list(Z)
    ordered_symbols = [corr_matrix.index[i] for i in leaves]
    return corr_matrix.loc[ordered_symbols, ordered_symbols]
