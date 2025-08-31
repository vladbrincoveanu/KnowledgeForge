"""
Utility functions and helpers.

This module contains common utility functions used throughout the application.
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize an object to JSON."""
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to serialize object to JSON: {e}")
        return str(obj)


def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp to ISO format."""
    return timestamp.isoformat() if timestamp else None


def validate_data_structure(data: dict[str, Any], required_fields: list[str]) -> bool:
    """Validate that required fields are present in data."""
    return all(field in data for field in required_fields)


def sanitize_string(input_string: str) -> str:
    """Sanitize input string for safe processing."""
    if not input_string:
        return ""

    # Remove potentially dangerous characters
    dangerous_chars = ["<", ">", '"', "'", "&"]
    sanitized = input_string

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")

    return sanitized.strip()


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split a list into chunks of specified size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]
