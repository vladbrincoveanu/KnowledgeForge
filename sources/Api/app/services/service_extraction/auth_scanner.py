"""Auth Scanner - Detects authentication types used by services."""

import logging
import re
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class AuthType(Enum):
    NONE = "None"
    JWT = "JWT"
    OAUTH = "OAuth"
    API_KEY = "API-Key"
    MTLS = "mTLS"
    BASIC = "Basic"
    CUSTOM = "Custom"


AUTH_NONE = AuthType.NONE
AUTH_JWT = AuthType.JWT
AUTH_OAUTH = AuthType.OAUTH
AUTH_APIKEY = AuthType.API_KEY
AUTH_MTLS = AuthType.MTLS
AUTH_BASIC = AuthType.BASIC


def scan_auth(repo_path: Path) -> list[str]:
    """Scan for authentication types used in the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        List of detected auth types (e.g., ["JWT", "OAuth"])
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return ["None"]

    auth_types = set()

    # Skip test files
    source_files = [f for f in repo_path.rglob("*.py") if "test" not in f.name.lower()]

    for f in source_files:
        try:
            content = f.read_text(errors="ignore")

            # JWT
            if re.search(r"jwt\.decode|JWT\(|from jwt import", content):
                auth_types.add("JWT")

            # OAuth
            if re.search(r"oauth|OAuth|AuthorizationCode|AccessToken", content, re.IGNORECASE):
                auth_types.add("OAuth")

            # API Key
            if re.search(r"api[_-]?key|X-Api-Key|apikey", content, re.IGNORECASE):
                auth_types.add("API-Key")

            # mTLS / Mutual TLS
            if re.search(r"mtls|mutual.*tls|cert.*key|ssl.*cert", content, re.IGNORECASE):
                auth_types.add("mTLS")

            # Basic Auth
            if re.search(r"Basic.*[Aa]uth|Authorization:.*Basic", content):
                auth_types.add("Basic")

        except Exception:
            continue

    # Check for auth config files
    env_file = repo_path / ".env"
    if env_file.exists():
        try:
            content = env_file.read_text()
            if "JWT" in content or "OAUTH" in content:
                auth_types.add("JWT")
            if "API_KEY" in content:
                auth_types.add("API-Key")
        except Exception:
            pass

    # Check OpenAPI specs
    openapi_files = list(repo_path.rglob("openapi*.json"))
    for of in openapi_files:
        try:
            content = of.read_text()
            if "jwt" in content.lower():
                auth_types.add("JWT")
            if "oauth" in content.lower():
                auth_types.add("OAuth")
            if "apikey" in content.lower():
                auth_types.add("API-Key")
        except Exception:
            continue

    if not auth_types:
        return ["None"]

    return sorted(auth_types)
