"""Core configuration module."""

from config.config import ExtractionConfig, LMStudioConfig, Neo4jConfig

def get_settings():
    """Get default configuration settings."""
    return {
        "extraction": ExtractionConfig(),
        "lmstudio": LMStudioConfig(),
        "neo4j": Neo4jConfig(),
        "environment": "development",
        "debug": True
    }

# Re-export for backward compatibility
__all__ = ["get_settings", "ExtractionConfig", "LMStudioConfig", "Neo4jConfig"]
