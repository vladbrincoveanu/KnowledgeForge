# OmniPay ML Pipeline

Owner: Vlas

This service provides machine learning pipelines for transaction risk scoring
and customer behavior prediction. It uses Hydra for configuration management
which requires specialized parsing to detect the ML framework.

## Technology

- Python 3.11
- Hydra for configuration management
- MLflow for experiment tracking
- PyTorch for model training
- FastAPI for serving predictions

## Configuration

Uses Hydra for hierarchical configuration:
- config.yml - Main config
- config/model.yaml - Model parameters
- config/data.yaml - Data processing

## Dependencies

- hydra-core>=1.3.0
- mlflow>=2.10.0
- torch>=2.1.0
- fastapi>=0.100.0
- scikit-learn>=1.3.0

## Environment Variables

- `MLFLOW_TRACKING_URI` - MLflow tracking server URL
- `MODEL_REGISTRY_PATH` - Path to model registry
