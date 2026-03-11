"""Feature engineering helpers for the fraud model."""

import pandas as pd


def build_feature_frame(payload: dict[str, object]) -> pd.DataFrame:
    """Create a one-row feature frame used by the scoring model."""
    amount = float(payload.get("amount", 0))
    card_country = str(payload.get("cardCountry", "unknown"))
    device_count = int(payload.get("deviceCountLast24h", 0))
    velocity = int(payload.get("txCountLast10m", 0))

    return pd.DataFrame(
        [
            {
                "amount": amount,
                "card_country": card_country,
                "device_count_last_24h": device_count,
                "tx_count_last_10m": velocity,
                "cross_border": card_country not in {"ro", "de", "at"},
            }
        ]
    )
