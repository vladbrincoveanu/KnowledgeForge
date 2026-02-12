"""Auth configuration scanner for context-level Actors field improvement.

Scans a service directory for authentication patterns beyond README analysis:
- OAuth 2.0 / OIDC configuration files and middleware
- API key middleware in application code
- OpenAPI/Swagger securitySchemes declarations
- Auth library imports (e.g. Flask-Login, Passport.js, Spring Security)
- JWT usage in code

Returns a list of detected auth mechanisms and inferred actor types.
Depends on API Surface Type being populated first (api_surface_types).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)

# ── Auth type constants ────────────────────────────────────────────────────────

AUTH_OAUTH = "OAuth2/OIDC"
AUTH_APIKEY = "APIKey"
AUTH_JWT = "JWT"
AUTH_BASIC = "BasicAuth"
AUTH_SESSION = "SessionCookie"
AUTH_MTLS = "mTLS"
AUTH_NONE = "None"

# ── File patterns for discovery ───────────────────────────────────────────────

_OPENAPI_FILES = {
    "openapi.yaml", "openapi.yml", "openapi.json",
    "swagger.yaml", "swagger.yml", "swagger.json",
}

_OAUTH_CONFIG_GLOBS = [
    "**/.env*", "**/config*.yml", "**/config*.yaml", "**/config*.json",
    "**/auth*.py", "**/auth*.ts", "**/auth*.js",
    "**/oauth*.py", "**/oauth*.ts",
    "**/keycloak*.json", "**/okta*.json",
]

# Code patterns: (pattern, auth_type)
_CODE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # OAuth / OIDC
    (re.compile(r"oauth2|oidc|openid.connect|keycloak|okta|auth0", re.I), AUTH_OAUTH),
    # JWT
    (re.compile(r"jwt\.decode|jwt\.encode|PyJWT|jsonwebtoken|verify_token", re.I), AUTH_JWT),
    # API keys
    (re.compile(r"api.?key|x-api-key|apikey|APIKeyHeader|APIKeyQuery", re.I), AUTH_APIKEY),
    # Basic auth
    (re.compile(r"BasicAuth|HTTPBasic|basic.?auth|Authorization.*Basic", re.I), AUTH_BASIC),
    # Session / cookies
    (re.compile(r"session\[.user|flask_login|passport\.session|express-session", re.I), AUTH_SESSION),
    # mTLS / client certs
    (re.compile(r"ssl_context|mutual.?tls|client.?cert|VERIFY_PEER", re.I), AUTH_MTLS),
]

# OpenAPI securitySchemes patterns
_OPENAPI_SECURITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"type:\s*oauth2", re.I), AUTH_OAUTH),
    (re.compile(r"type:\s*openIdConnect", re.I), AUTH_OAUTH),
    (re.compile(r"type:\s*apiKey", re.I), AUTH_APIKEY),
    (re.compile(r"type:\s*http", re.I), AUTH_BASIC),  # may also be bearer/JWT
    (re.compile(r"bearer|bearerFormat:\s*JWT", re.I), AUTH_JWT),
]

# Env-var hints
_ENV_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"OAUTH|CLIENT_ID|CLIENT_SECRET|OIDC", re.I), AUTH_OAUTH),
    (re.compile(r"JWT_SECRET|JWT_KEY|TOKEN_SECRET", re.I), AUTH_JWT),
    (re.compile(r"API_KEY|APIKEY", re.I), AUTH_APIKEY),
]

# Source file extensions to scan
_SOURCE_EXTS = {".py", ".ts", ".js", ".java", ".go", ".rb", ".php", ".cs"}


@dataclass
class AuthScanResult:
    """Result of scanning a service for authentication mechanisms."""

    auth_types: list[str] = field(default_factory=list)
    """Detected authentication mechanisms (deduplicated)."""

    actors: list[str] = field(default_factory=list)
    """Inferred actor types based on auth mechanisms."""

    evidence: list[str] = field(default_factory=list)
    """Evidence sources used (for auditing)."""


def _infer_actors(auth_types: list[str]) -> list[str]:
    """Infer actor types from detected auth mechanisms."""
    actors: list[str] = []
    if not auth_types or auth_types == [AUTH_NONE]:
        actors.append("Anonymous / Public")
        return actors
    if AUTH_OAUTH in auth_types:
        actors.append("Human User (SSO/OAuth)")
    if AUTH_APIKEY in auth_types:
        actors.append("External System (API key)")
    if AUTH_JWT in auth_types and AUTH_OAUTH not in auth_types:
        actors.append("Service-to-Service (JWT)")
    if AUTH_MTLS in auth_types:
        actors.append("Internal Service (mTLS)")
    if AUTH_BASIC in auth_types:
        actors.append("Human User (Basic)")
    if AUTH_SESSION in auth_types:
        actors.append("Human User (Session)")
    return actors or ["Unknown"]


def scan_auth(service_path: Path) -> AuthScanResult:
    """Scan a service directory for authentication patterns.

    Args:
        service_path: Root directory of the service.

    Returns:
        AuthScanResult with detected auth types and inferred actors.
    """
    if not service_path or not service_path.is_dir():
        return AuthScanResult(auth_types=[AUTH_NONE], actors=["Unknown"])

    detected: set[str] = set()
    evidence: list[str] = []

    # ── 1. OpenAPI / Swagger securitySchemes ──────────────────────────────────
    for fname in _OPENAPI_FILES:
        spec_file = service_path / fname
        if spec_file.exists():
            try:
                content = spec_file.read_text(encoding="utf-8", errors="ignore")
                for pattern, auth_type in _OPENAPI_SECURITY_PATTERNS:
                    if pattern.search(content):
                        detected.add(auth_type)
                        evidence.append(f"{fname}:securitySchemes ({auth_type})")
            except OSError:
                pass

    # ── 2. Source code scanning ───────────────────────────────────────────────
    source_files = limited_rglob(service_path, "*", max_files=800)
    scanned = 0
    for src_file in source_files:
        if src_file.suffix not in _SOURCE_EXTS:
            continue
        # Skip test files — they import auth libs but don't mean the service uses them
        if any(part in ("tests", "test", "__tests__", "spec") for part in src_file.parts):
            continue
        try:
            content = src_file.read_text(encoding="utf-8", errors="ignore")
            for pattern, auth_type in _CODE_PATTERNS:
                if pattern.search(content):
                    detected.add(auth_type)
                    evidence.append(f"{src_file.name} ({auth_type})")
            scanned += 1
        except OSError:
            pass
        if scanned >= 50:  # cap source files to avoid slow scans
            break

    # ── 3. Environment variable hints (.env* files) ───────────────────────────
    for env_file in limited_rglob(service_path, ".env*", max_files=10):
        try:
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            for pattern, auth_type in _ENV_PATTERNS:
                if pattern.search(content):
                    detected.add(auth_type)
                    evidence.append(f"{env_file.name} env-var ({auth_type})")
        except OSError:
            pass

    auth_types = sorted(detected) if detected else [AUTH_NONE]
    actors = _infer_actors(auth_types)

    return AuthScanResult(
        auth_types=auth_types,
        actors=actors,
        evidence=evidence[:10],  # cap evidence list
    )
