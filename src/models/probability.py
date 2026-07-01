from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split


def _chronological_train_test_split(
    data: pd.DataFrame,
    test_size: float,
    date_col: str = "date",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")

    ordered = data.sort_values(date_col).reset_index(drop=True) if date_col in data.columns else data.reset_index(drop=True)
    split_idx = int(len(ordered) * (1 - test_size))
    split_idx = max(1, min(split_idx, len(ordered) - 1))
    return ordered.iloc[:split_idx].copy(), ordered.iloc[split_idx:].copy()


def train_logistic_probability_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    categorical_cols: list[str] | None = None,
    test_size: float = 0.25,
    random_state: int = 42,
    split_method: str = "time",
    date_col: str = "date",
) -> tuple[Pipeline, dict]:
    categorical_cols = categorical_cols or []
    numeric_cols = [c for c in feature_cols if c not in categorical_cols]
    data = df.dropna(subset=[target_col]).copy()

    if len(data) < 2:
        raise ValueError("At least two rows are required to train and evaluate the model")

    if split_method == "time":
        train_data, test_data = _chronological_train_test_split(data, test_size=test_size, date_col=date_col)
    elif split_method == "random":
        X = data[feature_cols]
        y = data[target_col].astype(int)
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=y if y.nunique() == 2 else None,
        )
        train_data = X_train.copy()
        train_data[target_col] = y_train.values
        test_data = X_test.copy()
        test_data[target_col] = y_test.values
    else:
        raise ValueError("split_method must be either 'time' or 'random'")

    X_train = train_data[feature_cols]
    X_test = test_data[feature_cols]
    y_train = train_data[target_col].astype(int)
    y_test = test_data[target_col].astype(int)

    if y_train.nunique() < 2:
        raise ValueError("Training split must contain at least two classes for logistic regression")

    preprocessor = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_cols),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_cols),
    ])
    model = Pipeline([
        ("preprocess", preprocessor),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba)) if y_test.nunique() == 2 else None,
        "classification_report": classification_report(y_test, pred, output_dict=True, zero_division=0),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "split_method": split_method,
    }
    return model, metrics
