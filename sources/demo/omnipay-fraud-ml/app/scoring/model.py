"""Demo risk model implementation."""

import pandas as pd


def score_transaction(feature_frame: pd.DataFrame) -> float:
    """Return a simple deterministic score for the demo workspace."""
    row = feature_frame.iloc[0]

    risk_score = 0.15
    if row["amount"] > 5000:
        risk_score += 0.35
    if row["device_count_last_24h"] > 3:
        risk_score += 0.2
    if row["tx_count_last_10m"] > 5:
        risk_score += 0.2
    if row["cross_border"]:
        risk_score += 0.1

    return round(min(risk_score, 0.99), 2)
