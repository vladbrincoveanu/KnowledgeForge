"""Core configuration module."""

from config.config import get_settings

# Re-export for backward compatibility
__all__ = ["get_settings"]
