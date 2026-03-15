"""ML Pipeline service using Hydra configuration."""

import os
import pickle
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import torch.nn as nn
from omegaconf import OmegaConf

app = FastAPI(title="OmniPay ML Pipeline")

# Load config using Hydra pattern
config_path = Path(__file__).parent / "config" / "config.yaml"
if config_path.exists():
    config = OmegaConf.load(config_path)
else:
    config = OmegaConf.create({})


class RiskScoreRequest(BaseModel):
    amount: float
    currency: str
    merchant_category: str
    account_age_days: int


class TransactionFeatureExtractor:
    """Extract features from transaction data."""

    def extract(self, data: dict) -> list:
        """Convert transaction data to feature vector."""
        features = [
            data.get("amount", 0),
            hash(data.get("currency", "")) % 100,
            hash(data.get("merchant_category", "")) % 50,
            data.get("account_age_days", 0) / 365.0,
        ]
        return features


class RiskModel(nn.Module):
    """Simple neural network for risk scoring."""

    def __init__(self, input_dim=4):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.fc(x)


# Initialize model (in real app, load from registry)
model = RiskModel()
model.eval()


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ml-pipeline",
        "config_loaded": bool(config),
    }


@app.get("/config")
def get_config():
    """Expose current configuration (without secrets)."""
    return OmegaConf.to_container(config, resolve=True)


@app.post("/api/v1/predict/risk")
def predict_risk(request: RiskScoreRequest):
    """Predict transaction risk score."""
    extractor = TransactionFeatureExtractor()
    features = extractor.extract(request.dict())

    with torch.no_grad():
        tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        score = model(tensor).item()

    return {
        "risk_score": score,
        "threshold": 0.5,
        "decision": "approve" if score < 0.5 else "review",
    }


@app.post("/api/v1/training/start")
def start_training():
    """Trigger model training (placeholder)."""
    return {
        "status": "started",
        "job_id": "training-12345",
        "config": OmegaConf.to_container(config.get("training", {}), resolve=True),
    }


@app.get("/api/v1/models")
def list_models():
    """List available models."""
    return {
        "models": [
            {"name": "risk-v1", "version": "1.0.0", "status": "production"},
            {"name": "risk-v2", "version": "2.0.0", "status": "staging"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
