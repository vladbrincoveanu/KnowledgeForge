"""Deterministic LLM doubles for container enrichment tests."""

import json
from typing import Any, Dict


class FakeOmniPayLLM:
    """Deterministic LLM double for container enrichment tests."""

    def __init__(self) -> None:
        self.timeout = 30

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 0,
        temperature: float = 0.0,
        use_cache: bool = True,
    ) -> str:
        del max_tokens, temperature, use_cache

        if "C4 CONTAINER DEFINITION" not in prompt:
            return "OmniPay is a demo payment platform with multiple service boundaries."

        return json.dumps(
            {
                "containers": [
                    {
                        "name": "omnipay-billing-llm",
                        "verdict": "keep",
                        "container_type": "Billing Service",
                        "technology": "Python/FastAPI",
                        "protocol": "HTTP",
                        "description": (
                            "Handles subscription billing, invoice generation, "
                            "refunds, and payment reconciliation workflows."
                        ),
                        "confidence": 0.91,
                        "notes": (
                            "Derived from billing and ledger signals in README and code."
                        ),
                    },
                    {
                        "name": "omnipay-ml-pipeline",
                        "verdict": "keep",
                        "container_type": "ML Pipeline",
                        "technology": "Python/Hydra/MLflow/PyTorch",
                        "protocol": "HTTP",
                        "description": (
                            "Runs risk-scoring training and inference workflows "
                            "backed by Hydra-managed ML configuration."
                        ),
                        "confidence": 0.93,
                        "notes": (
                            "Hydra config and MLflow markers indicate ML orchestration."
                        ),
                    },
                ],
                "inferred_relationships": [],
            }
        )
