# 📁 Extraction Output Storage

## Location

Extraction results are stored in JSON files at:

```
sources/Api/data/extractions/{task_id}/
├── metadata.json      # Task metadata, timestamps, status
├── services.json      # All extracted services (with 5 primary fields)
├── connections.json   # Service connections/relationships
└── summary.json       # Human-readable summary
```

**Full Path:**
```
/Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/data/extractions/{task_id}/
```

## Current Status

✅ **Storage is configured correctly:**
- `STORE_TO_JSON: True` (enabled)
- `STORE_TO_NEO4J: False` (disabled)
- Directory exists and is writable: `sources/Api/data/extractions/`

⚠️ **Directory is currently empty** - This means:
- No extractions have completed yet, OR
- Extractions failed before reaching the storage step

## How to Check

### 1. List All Extraction Tasks

```bash
# List all task directories
ls -la sources/Api/data/extractions/

# Find all JSON files
find sources/Api/data/extractions -name "*.json" -type f
```

### 2. Check Task Status via API

```bash
# Get task status
curl "http://localhost:8000/api/v1/services/extraction/{task_id}"

# Get full results (includes JSON file paths)
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/results"
```

### 3. View Services JSON

```bash
# View services.json for a specific task
cat sources/Api/data/extractions/{task_id}/services.json | jq

# View summary
cat sources/Api/data/extractions/{task_id}/summary.json | jq '.statistics'
```

### 4. Download JSON Files via API

```bash
# Download services.json
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/json/services" \
  -o services.json

# Download summary.json
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/json/summary" \
  -o summary.json
```

## Services JSON Structure

Each `services.json` file contains:

```json
{
  "task_id": "20240117-123456-abc123",
  "total_services": 5,
  "extracted_at": "2024-01-17T12:34:56",
  "services": [
    {
      // ═══════════════════════════════════════════════════════════
      // THE 5 PRIMARY EXTRACTION FIELDS
      // ═══════════════════════════════════════════════════════════
      "domain": "payments",
      "owner": "John Doe",
      "owner_contributors": ["john@example.com", "jane@example.com"],
      "owner_contributor_stats": [
        {
          "email": "john@example.com",
          "name": "John Doe",
          "commit_count": 45
        }
      ],
      "contributor_count": 3,
      "status": "Active-Dev",
      "status_evidence": {
        "commits_30d": 12,
        "commits_90d": 34,
        "last_commit_date": "2024-01-15T10:30:00"
      },
      "tier": "Tier 1",
      "data_class": "PII",
      
      // Service identity
      "id": "svc-payment-service",
      "name": "payment-service",
      "display_name": "Payment Service",
      "description": "Handles payment processing",
      "notes": "Processes credit card transactions and payment validation.",
      
      // Technical details
      "language": "Python",
      "framework": "FastAPI",
      "file_path": "services/payment",
      
      // Dependencies
      "direct_depends": ["svc-auth-service"],
      "dependencies": ["svc-auth-service"],
      "dependents": ["svc-checkout-service"],
      
      // Git activity
      "last_commit_date": "2024-01-15T10:30:00",
      "commit_count_30d": 12,
      "commit_count_90d": 34,
      "commit_count_180d": 67
    }
  ]
}
```

## Configuration

Storage is controlled by environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KF_STORE_TO_JSON` | `true` | Enable JSON file storage |
| `KF_STORE_TO_NEO4J` | `false` | Enable Neo4j storage |
| `KF_JSON_OUTPUT_DIR` | `data/extractions` | Output directory (relative to Api/) |

## Next Steps

To generate extraction output:

1. **Run an extraction** via API:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/services/extract-from-github" \
     -H "Content-Type: application/json" \
     -d '{"github_url": "https://github.com/owner/repo"}'
   ```

2. **Get the task_id** from the response

3. **Wait for completion** (check status endpoint)

4. **View results**:
   ```bash
   # Check if files exist
   ls -la sources/Api/data/extractions/{task_id}/
   
   # View services
   cat sources/Api/data/extractions/{task_id}/services.json | jq
   ```

## Troubleshooting

### Files Not Created?

1. **Check extraction status:**
   ```bash
   curl "http://localhost:8000/api/v1/services/extraction/{task_id}"
   ```

2. **Check logs** for errors during extraction

3. **Verify STORE_TO_JSON is enabled:**
   ```python
   from app.services.service_extraction.extraction_config import ExtractionConfig
   print(ExtractionConfig.STORE_TO_JSON)  # Should be True
   ```

4. **Check directory permissions:**
   ```bash
   ls -la sources/Api/data/extractions/
   ```

### Files Exist But Empty?

- Extraction may have found 0 services
- Check `metadata.json` for errors/warnings
- Review extraction logs
