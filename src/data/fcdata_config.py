"""Configuration module compatible with SSI `MarketDataClient`.

The official SSI sample passes a Python module named `config` containing
`auth_type`, `consumerID`, `consumerSecret`, `url`, and `stream_url`.
This module provides the same attributes but reads secrets from `.env`.
"""

import os
from dotenv import load_dotenv

load_dotenv()

auth_type = "Bearer"
consumerID = os.getenv("SSI_CONSUMER_ID", "")
consumerSecret = os.getenv("SSI_CONSUMER_SECRET", "")
url = os.getenv("SSI_URL", "https://fc-data.ssi.com.vn/")
stream_url = os.getenv("SSI_STREAM_URL", "https://fc-datahub.ssi.com.vn/")


def validate_config() -> None:
    """Raise a clear error when FCData credentials are missing."""
    missing = []
    if not consumerID:
        missing.append("SSI_CONSUMER_ID")
    if not consumerSecret:
        missing.append("SSI_CONSUMER_SECRET")
    if missing:
        raise EnvironmentError(
            "Missing FCData credential(s): " + ", ".join(missing) +
            ". Create `.env` from `.env.example` and fill in your SSI keys."
        )
