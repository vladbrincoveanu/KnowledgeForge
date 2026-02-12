"""Shared helper functions for service field extraction."""

import logging
import re
from pathlib import Path
from typing import Optional

import yaml
import json

from app.domain.models.services import Service, ServiceStatus, ServiceTier

logger = logging.getLogger(__name__)


def safe_read_file(file_path: Path, warnings: list[str]) -> Optional[str]:
    """Safely read file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except (OSError, ValueError) as e:
        warnings.append(f"Failed to read {file_path}: {e}")
        return None


def extract_field_value(
    labels: dict,
    env: dict,
    config: dict,
    field_names: list[str]
) -> Optional[str]:
    """
    Extract a field value from labels, environment, or config.
    Tries multiple possible field names.
    """
    # Try labels first
    if isinstance(labels, dict):
        for name in field_names:
            value = labels.get(name)
            if value:
                return str(value)

    # Try environment variables (uppercase versions)
    if isinstance(env, dict):
        for name in field_names:
            upper_name = name.upper()
            value = env.get(upper_name) or env.get(name)
            if value:
                return str(value)

    # Try config directly
    if isinstance(config, dict):
        for name in field_names:
            value = config.get(name)
            if value:
                return str(value)

    return None


def extract_status(
    labels: dict,
    env: dict,
    config: dict
) -> ServiceStatus:
    """
    Extract service status from labels, environment, or config.

    Maps to: ACTIVE, MAINTENANCE, DEPRECATED, ARCHIVED
    """
    status_value = extract_field_value(
        labels, env, config,
        ['status', 'service_status', 'lifecycle', 'lifecycle_status', 'state']
    )

    if not status_value:
        return ServiceStatus.UNKNOWN

    status_str = status_value.lower()

    if any(keyword in status_str for keyword in [
        'deprecated', 'sunset', 'retired', 'frozen', 'shutdown', 'legacy', 'end-of-life', 'eol'
    ]):
        return ServiceStatus.DEPRECATED

    if any(keyword in status_str for keyword in [
        'maintenance', 'maint', 'stable', 'support', 'bugfix', 'sustaining'
    ]):
        return ServiceStatus.MAINTENANCE

    if any(keyword in status_str for keyword in [
        'active', 'dev', 'development', 'running', 'live', 'production', 'prod'
    ]):
        return ServiceStatus.ACTIVE

    return ServiceStatus.UNKNOWN


def extract_tier(
    labels: dict,
    env: dict,
    config: dict
) -> ServiceTier:
    """
    Extract service criticality tier from labels, environment, or config.

    Maps to: Tier 1 (site-wide), Tier 2 (journey), Tier 3 (minor)
    """
    tier_value = extract_field_value(
        labels, env, config,
        ['tier', 'criticality', 'priority', 'sla_tier', 'service_tier', 'severity']
    )

    if not tier_value:
        return ServiceTier.UNKNOWN

    tier_str = tier_value.lower().strip()

    if any(keyword in tier_str for keyword in [
        'tier 1', 'tier1', 't1', 'critical', 'p1', 'p0', 'high', 'site-wide', 'sitewide'
    ]):
        return ServiceTier.TIER_1

    if any(keyword in tier_str for keyword in [
        'tier 2', 'tier2', 't2', 'important', 'p2', 'medium', 'journey'
    ]):
        return ServiceTier.TIER_2

    if any(keyword in tier_str for keyword in [
        'tier 3', 'tier3', 't3', 'minor', 'p3', 'low', 'cosmetic'
    ]):
        return ServiceTier.TIER_3

    # Try to parse numeric tier
    try:
        tier_num = int(tier_str.replace('tier', '').replace('t', '').strip())
        if tier_num == 1:
            return ServiceTier.TIER_1
        elif tier_num == 2:
            return ServiceTier.TIER_2
        elif tier_num >= 3:
            return ServiceTier.TIER_3
    except ValueError:
        pass

    return ServiceTier.UNKNOWN


def resolve_service_path(repo_root: Path, service: Service) -> Optional[Path]:
    """
    Resolve the filesystem path for a service based on known metadata.

    Prefers the recorded file_path; falls back to a directory matching the
    service name if the recorded path is missing.
    """
    if service.file_path:
        potential_path = repo_root / service.file_path
        if potential_path.exists():
            return potential_path
        fallback = repo_root / service.name
        if fallback.exists() and fallback.is_dir():
            return fallback
    else:
        potential_path = repo_root / service.name
        if potential_path.exists() and potential_path.is_dir():
            return potential_path
    return None


def is_missing_label(value: Optional[str]) -> bool:
    """Detect missing label values."""
    if not value:
        return True
    if not isinstance(value, str):
        return True
    lowered = value.strip().lower()
    return lowered in {"unknown", "unclassified", "none", "n/a", "null"}


def normalize_status_label(value: Optional[str]) -> Optional[ServiceStatus]:
    """Convert string status to ServiceStatus enum."""
    if not value:
        return None
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    if any(token in lowered for token in ["deprecat", "sunset", "retire", "frozen", "legacy", "eol"]):
        return ServiceStatus.DEPRECATED
    if any(token in lowered for token in ["maint", "bugfix", "support", "stabil", "patch"]):
        return ServiceStatus.MAINTENANCE
    if any(token in lowered for token in ["active", "dev", "feature"]):
        return ServiceStatus.ACTIVE
    if lowered in {"unknown", "unclassified", "n/a", "null"}:
        return None
    return None


def normalize_tier_label(value: Optional[str]) -> Optional[ServiceTier]:
    """Convert string tier to ServiceTier enum."""
    if not value:
        return None
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    if any(token in lowered for token in ["tier 1", "tier1", "t1", "critical", "p0", "p1"]):
        return ServiceTier.TIER_1
    if any(token in lowered for token in ["tier 2", "tier2", "t2", "important", "p2", "medium"]):
        return ServiceTier.TIER_2
    if any(token in lowered for token in ["tier 3", "tier3", "t3", "minor", "p3", "low"]):
        return ServiceTier.TIER_3
    if lowered in {"unknown", "unclassified", "n/a", "null"}:
        return None
    return None


def extract_five_fields_from_config(
    config_data: dict,
    labels: dict | None = None,
    env: dict | None = None,
) -> dict:
    """
    Extract the 5 primary service fields from a config dict.

    Returns dict with keys: domain, owner, status, tier, data_class
    """
    labels = labels or {}
    env = env or {}

    domain = extract_field_value(labels, env, config_data, ['domain', 'business_domain', 'area'])
    owner = extract_field_value(labels, env, config_data, ['owner', 'team', 'squad', 'maintainer'])
    status = extract_status(labels, env, config_data)
    tier = extract_tier(labels, env, config_data)
    data_class = extract_field_value(
        labels, env, config_data,
        ['data_class', 'dataClass', 'data-class', 'data_classification', 'sensitivity', 'data_sensitivity', 'pii_level']
    )

    return {
        'domain': domain,
        'owner': owner,
        'status': status,
        'tier': tier,
        'data_class': data_class,
    }


def extract_fields_from_code(content: str) -> dict:
    """
    Extract the 5 primary fields from code comments/annotations.

    Returns dict with keys: domain, owner, status, tier, data_class.
    Values may be None.
    """
    field_patterns = {
        'domain': r'domain\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
        'owner': r'(?:owner|team|squad)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
        'status': r'status\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
        'tier': r'(?:tier|criticality)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
        'data_class': r'data_class\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
    }

    result = {'domain': None, 'owner': None, 'status': None, 'tier': None, 'data_class': None}

    for field_name, pattern in field_patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            value = match.group(1)
            if field_name == 'status':
                result['status'] = extract_status({'status': value}, {}, {})
            elif field_name == 'tier':
                result['tier'] = extract_tier({'tier': value}, {}, {})
            else:
                result[field_name] = value

    return result
