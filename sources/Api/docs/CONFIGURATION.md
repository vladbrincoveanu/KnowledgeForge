# KnowledgeForge API Configuration Guide

## Overview

The KnowledgeForge API uses a streamlined configuration system that eliminates duplication and provides a clean, maintainable way to manage application settings.

## Configuration Structure

### Main Configuration File (`config.yaml`)

The main configuration file contains all application settings organized in logical sections:

```yaml
# Environment settings
environment: "development"
debug: true

# Neo4j database configuration
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "password"
  database: "neo4j"

# LM Studio LLM service configuration
lmstudio:
  base_url: "http://localhost:1234"
  model_name: "deepseek/deepseek-r1-0528-qwen3-8b"
  temperature: 0.7

# And more...
```

### Configuration Classes (`utils/config.py`)

The configuration is managed through Pydantic models that provide:

- **Type validation**: All values are validated against their expected types
- **Default values**: Sensible defaults for all settings
- **Environment variable support**: Override config via environment variables
- **File loading**: Automatic loading from YAML files
- **Validation**: Built-in validation and error checking

## Usage

### Basic Usage

```python
from utils.config import config

# Access configuration values
neo4j_uri = config.neo4j.uri
model_name = config.lmstudio.model_name
confidence_threshold = config.extraction.confidence_threshold
```

### Using Convenience Aliases

```python
from utils.settings import neo4j_config, llm_config

# More concise access
uri = neo4j_config.uri
model = llm_config.model_name
```

### Environment Variable Overrides

You can override any configuration value using environment variables:

```bash
# Override Neo4j URI
export KF_NEO4J__URI="bolt://neo4j.example.com:7687"

# Override LM Studio base URL
export KF_LMSTUDIO__BASE_URL="https://llm.example.com"

# Override debug mode
export KF_DEBUG="false"
```

**Note**: Use `KF_` prefix and `__` for nested configuration (e.g., `KF_NEO4J__URI` for `neo4j.uri`).

### Loading Custom Config Files

```python
from utils.config import get_config

# Load from specific file
config = get_config("path/to/custom-config.yaml")
```

## Configuration Sections

### Neo4j Configuration
- Database connection settings
- Connection pool configuration
- Security settings

### LM Studio Configuration
- LLM service endpoint
- Model parameters
- Embedding settings

### Extraction Configuration
- Confidence thresholds
- Batch processing settings
- Feature toggles

### Metadata Storage Configuration
- DuckDB settings
- Caching configuration
- Backup settings

### Logging Configuration
- Log levels and formats
- File and console logging
- Log rotation settings

### Security Configuration
- API key requirements
- Rate limiting
- CORS settings

## Validation

The configuration system automatically validates:

- Required fields
- Value ranges (e.g., thresholds between 0-1)
- URI formats
- File paths
- Enum values

## Best Practices

1. **Use the main config file** for development and testing
2. **Use environment variables** for production deployments
3. **Keep sensitive data** (passwords, API keys) in environment variables
4. **Validate configuration** before starting the application
5. **Use type hints** when accessing config values in your code

## Migration from Old System

The old configuration system had duplicate files (`config.py` and `settings.py`). The new system:

- ✅ Eliminates duplication
- ✅ Provides cleaner API
- ✅ Maintains backward compatibility
- ✅ Improves validation
- ✅ Simplifies maintenance

## Example Configuration

See `config.yaml` for a complete example of all available configuration options.
