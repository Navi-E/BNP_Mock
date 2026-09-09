from pathlib import Path
import joblib
import pandas as pd
import numpy as np


# ---------------------------------------------------------
# MODEL LOCATION
# ---------------------------------------------------------

MODEL_PATH = Path(__file__).resolve().parent / "ml_scorer.pkl"


# ---------------------------------------------------------
# EXACT 21 FEATURES USED BY THE TRAINED RANDOM FOREST
# ---------------------------------------------------------

DEFAULT_FEATURES = [
    "amount",
    "sender_transaction_count",
    "receiver_transaction_count",
    "cross_border",
    "structuring_flag",
    "time_since_previous_sender_txn",
    "rapid_transaction_flag",
    "sender_in_degree",
    "sender_out_degree",
    "receiver_in_degree",
    "receiver_out_degree",
    "sender_pagerank",
    "receiver_pagerank",
    "sender_betweenness",
    "receiver_betweenness",
    "sender_cycle_participation",
    "receiver_cycle_participation",
    "sender_in_out_degree_ratio",
    "receiver_in_out_degree_ratio",
    "dwell_time_latency",
    "balance_retention_rate",
]


# ---------------------------------------------------------
# LOAD RANDOM FOREST MODEL
# ---------------------------------------------------------

def load_model():
    """
    Load the trained Random Forest model from ml_scorer.pkl.
    """

    if not MODEL_PATH.exists():
        return None

    return joblib.load(MODEL_PATH)


# ---------------------------------------------------------
# PREDICT AML RISK
# ---------------------------------------------------------

def predict(model, feature_row):
    """
    Run Random Forest prediction on one transaction.

    feature_row must contain all 21 DEFAULT_FEATURES.
    """

    if model is None:
        return {
            "prediction": None,
            "probability": None,
            "rf_risk": None,
            "model_status": "Random Forest model not found",
        }

    # Make sure features are supplied in exactly
    # the same order as during model training.
    X = pd.DataFrame(
        [[feature_row[name] for name in DEFAULT_FEATURES]],
        columns=DEFAULT_FEATURES,
    )

    X = X.replace([np.inf, -np.inf], 0).fillna(0)

    prediction = int(model.predict(X)[0])

    probability = None

    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(X)[0][1])

    rf_risk = None

    if probability is not None:
        rf_risk = round(probability * 100, 2)

    return {
        "prediction": prediction,
        "probability": round(probability, 6)
        if probability is not None
        else None,
        "rf_risk": rf_risk,
        "model_status": "connected",
    }