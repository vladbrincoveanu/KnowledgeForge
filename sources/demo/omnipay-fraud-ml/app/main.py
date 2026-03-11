"""Fraud scoring API for OmniPay."""

from fastapi import FastAPI

from app.scoring.features import build_feature_frame
from app.scoring.model import score_transaction

app = FastAPI(title="OmniPay Fraud ML", version="1.0.0")


@app.post("/v1/risk/score")
def score(payload: dict[str, object]) -> dict[str, object]:
    """Score a transaction and return a deterministic demo result."""
    feature_frame = build_feature_frame(payload)
    risk_score = score_transaction(feature_frame)
    return {
        "transactionId": payload.get("transactionId"),
        "riskScore": risk_score,
        "decision": "review" if risk_score > 0.6 else "approve",
    }


@app.post("/v1/risk/feedback")
def capture_feedback(payload: dict[str, object]) -> dict[str, object]:
    """Accept analyst feedback for future retraining."""
    return {
        "transactionId": payload.get("transactionId"),
        "label": payload.get("label", "unknown"),
        "accepted": True,
    }
