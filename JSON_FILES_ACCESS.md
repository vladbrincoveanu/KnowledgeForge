# Accessing Extraction JSON Files

## 📁 File Location

JSON files are saved to:
```
sources/data/extractions/{task_id}/
├── metadata.json      # Task metadata, timestamps, status
├── services.json      # All extracted services with the 5 primary fields
├── connections.json   # Service connections/relationships
└── summary.json       # Human-readable summary
```

**Example:**
```
sources/data/extractions/54a4c5a9-e925-479e-b7d1-37ba7f1c943c/
├── metadata.json
├── services.json
├── connections.json
└── summary.json
```

## 🌐 Via API

### 1. Get Results (includes JSON file paths)

```bash
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/results"
```

**Response includes:**
```json
{
  "json_files": {
    "metadata": {
      "container_path": "/app/data/extractions/{task_id}/metadata.json",
      "host_path": "sources/data/extractions/{task_id}/metadata.json",
      "download_url": "/api/v1/services/extraction/{task_id}/json/metadata"
    },
    "services": { ... },
    "connections": { ... },
    "summary": { ... }
  }
}
```

### 2. Download JSON Files

```bash
# Download services.json
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/json/services" \
  -o services.json

# Download summary.json
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/json/summary" \
  -o summary.json

# Download all files
for file in metadata services connections summary; do
  curl "http://localhost:8000/api/v1/services/extraction/{task_id}/json/$file" \
    -o "${file}.json"
done
```

## 🖥️ Direct File Access

Since the `data` directory is mounted as a volume, you can access files directly:

```bash
# View services.json
cat sources/data/extractions/{task_id}/services.json | jq

# View summary
cat sources/data/extractions/{task_id}/summary.json | jq

# List all extraction tasks
ls -la sources/data/extractions/
```

## 🎨 In the UI

The UI should display JSON file download links when viewing extraction results. The `json_files` object in the results response contains download URLs for each file.

**Example UI Integration:**
```typescript
const results = await serviceExtractionAPI.getExtractionResults(taskId);

// Display download links
if (results.json_files) {
  Object.entries(results.json_files).forEach(([type, info]) => {
    console.log(`Download ${type}: ${info.download_url}`);
  });
}
```

## 📊 File Contents

### services.json
Contains all extracted services with:
- The 5 primary fields (domain, owner, status, tier, data_class)
- Owner contributors list
- Status evidence (commit stats)
- Direct dependencies
- Git activity metrics
- Commit counts (30d, 90d, 180d)

### summary.json
Human-readable summary with:
- Statistics (total services, by status, by domain, by tier)
- Services overview (quick scan of the 5 fields)
- Output file paths

### connections.json
Service connections/relationships with:
- Source/target service IDs
- Connection types
- Protocols and endpoints
- Strength and confidence

### metadata.json
Task metadata:
- Task ID, status
- Repository URL/name
- Timestamps
- Errors and warnings

---

## 🔍 Quick Test

```bash
# 1. Extract from GitHub
TASK_ID=$(curl -s -X POST "http://localhost:8000/api/v1/services/extract-from-github" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/shuup/shuup", "use_git": true}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['task_id'])")

# 2. Wait for completion (check status)
curl "http://localhost:8000/api/v1/services/extraction/$TASK_ID"

# 3. Get results with JSON file paths
curl "http://localhost:8000/api/v1/services/extraction/$TASK_ID/results" | jq '.json_files'

# 4. Download services.json
curl "http://localhost:8000/api/v1/services/extraction/$TASK_ID/json/services" \
  -o services.json

# 5. View locally
cat sources/data/extractions/$TASK_ID/services.json | jq '.services[0]'
```



