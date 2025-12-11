# Service Extraction Guide

Extract services from GitHub repositories or ZIP files. **Services are nodes** in the graph, and we extract **5 primary fields** for each service.

## The 5 Primary Fields

| # | Field | Meaning | Example Values |
|---|-------|---------|----------------|
| 1 | **domain** | Business area this service belongs to | `Revenue Core`, `Checkout`, `Identity`, `Logging` |
| 2 | **owner** | Squad/team that owns and supports the service | `Growth Squad`, `Platform Team`, `Payments Pod` |
| 3 | **status** | Where the service is in its lifecycle | `Active-Dev`, `Maintenance-Only`, `Deprecated / Frozen` |
| 4 | **tier** | Criticality - how bad if this breaks? | `Tier 1` (site-wide), `Tier 2` (journey), `Tier 3` (minor) |
| 5 | **data_class** | What sensitive data lives here? | `PII`, `Credit-Card`, `Public`, `Internal` |

## Quick Start

### 1. Start the API Server

```bash
cd sources/Api
python app.py
```

### 2. Extract from GitHub

```bash
curl -X POST "http://localhost:8000/api/v1/services/extract-from-github" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/owner/repo"}'
```

**Note:** Use a specific repository URL (e.g., `https://github.com/shuup/shuup`), not an organization page.

### 3. Check Status

```bash
curl "http://localhost:8000/api/v1/services/extraction/{task_id}"
```

### 4. Get Results

```bash
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/results"
```

**Response:**
```json
{
  "services": [
    {
      "name": "checkout-api",
      "domain": "Revenue Core",
      "owner": "Growth Squad",
      "status": "Active-Dev",
      "tier": "Tier 1",
      "data_class": "Credit-Card"
    }
  ],
  "connections": [...]
}
```

## How to Define the 5 Fields in Your Codebase

The extractor looks for these fields in multiple locations. Here's how to define them:

### Docker Compose Labels

```yaml
# docker-compose.yml
services:
  checkout-api:
    image: checkout:latest
    labels:
      domain: "Revenue Core"
      owner: "Growth Squad"
      status: "active-dev"
      tier: "tier1"
      data_class: "Credit-Card"
```

### Docker Compose Environment Variables

```yaml
services:
  checkout-api:
    environment:
      - DOMAIN=Revenue Core
      - OWNER=Growth Squad
      - STATUS=active
      - TIER=1
      - DATA_CLASS=Credit-Card
```

### Kubernetes Annotations/Labels

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  annotations:
    domain: "Revenue Core"
    owner: "Growth Squad"
    status: "active-dev"
    tier: "tier1"
    data_class: "Credit-Card"
```

### Service Configuration Files

```yaml
# service.yaml or services.yaml
services:
  checkout-api:
    domain: Revenue Core
    owner: Growth Squad
    status: active-dev
    tier: tier1
    data_class: Credit-Card
```

```json
// service.json or config.json
{
  "domain": "Revenue Core",
  "owner": "Growth Squad",
  "status": "active-dev",
  "tier": "tier1",
  "data_class": "Credit-Card"
}
```

### package.json (for Node.js services)

```json
{
  "name": "checkout-api",
  "domain": "Revenue Core",
  "owner": "Growth Squad",
  "status": "active-dev",
  "tier": "tier1",
  "data_class": "Credit-Card"
}
```

## Status Values

The extractor determines status from **two sources**:

### 1. Configuration Files
Recognizes these status keywords in config:

| Status | Keywords Matched |
|--------|-----------------|
| **Active-Dev** | `active`, `dev`, `development`, `running`, `live`, `prod`, `production` |
| **Maintenance-Only** | `maintenance`, `maint`, `stable`, `support`, `bugfix`, `sustaining` |
| **Deprecated / Frozen** | `deprecated`, `sunset`, `retired`, `frozen`, `shutdown`, `legacy`, `eol` |

### 2. Git Commit History (Automatic)
If status is not found in config, the extractor analyzes git log:

| Status | Git Activity Pattern |
|--------|---------------------|
| **Active-Dev** | Recent commits (<30 days), frequent activity (3+ commits) |
| **Maintenance-Only** | Old commits (30-180 days), only bugfix/maintenance keywords |
| **Deprecated / Frozen** | Very old commits (>180 days) OR deprecation keywords in commit messages |

**Git Analysis Features:**
- Analyzes commit frequency and recency
- Checks for deprecation keywords in commit messages
- Overrides config-based status if git suggests different (e.g., config says "active" but no commits in 6 months)
- Works per-service directory/file path

## Tier Values

The extractor recognizes these tier keywords:

| Tier | Keywords Matched |
|------|-----------------|
| **Tier 1** (Site-wide) | `tier 1`, `tier1`, `t1`, `critical`, `p1`, `p0`, `high`, `site-wide` |
| **Tier 2** (Journey) | `tier 2`, `tier2`, `t2`, `important`, `p2`, `medium`, `journey` |
| **Tier 3** (Minor) | `tier 3`, `tier3`, `t3`, `minor`, `p3`, `low`, `cosmetic` |

## View in UI

1. Start the UI: `cd sources/UI && npm run dev`
2. Open `http://localhost:5173`
3. Navigate to **Graph View** or **Architecture Map**
4. Services appear as nodes with the 5 fields displayed

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/services/extract-from-github` | Extract from GitHub URL |
| POST | `/api/v1/services/extract-from-zip` | Extract from ZIP file |
| POST | `/api/v1/services/extract-from-path` | Extract from local path |
| GET | `/api/v1/services/extraction/{task_id}` | Get extraction status |
| GET | `/api/v1/services/extraction/{task_id}/results` | Get extraction results |
| DELETE | `/api/v1/services/extraction/{task_id}` | Delete extraction task |

## Python Script Example

```python
import requests
import time

# Start extraction
r = requests.post("http://localhost:8000/api/v1/services/extract-from-github", 
    json={"github_url": "https://github.com/shuup/shuup"})
task_id = r.json()["task_id"]

# Wait for completion
while True:
    status = requests.get(f"http://localhost:8000/api/v1/services/extraction/{task_id}").json()
    print(f"Progress: {status.get('progress', 0)*100:.0f}%")
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(2)

# Get results with the 5 fields
results = requests.get(f"http://localhost:8000/api/v1/services/extraction/{task_id}/results").json()

print(f"\n✅ Found {len(results['services'])} services:\n")
for svc in results['services']:
    print(f"  📦 {svc['name']}")
    print(f"     domain:     {svc.get('domain', 'N/A')}")
    print(f"     owner:      {svc.get('owner', 'N/A')}")
    print(f"     status:     {svc.get('status', 'N/A')}")
    print(f"     tier:       {svc.get('tier', 'N/A')}")
    print(f"     data_class: {svc.get('data_class', 'N/A')}")
    print()
```

## Troubleshooting

### "Invalid GitHub URL"
Use `https://github.com/owner/repo` format, not organization pages.

### "No services found"
- Add `docker-compose.yml` or `kubernetes/` manifests
- Or add `service.yaml` / `service.json` config files
- Or structure as microservices in `services/` or `apps/` directories

### "Fields show as 'unknown' or 'N/A'"
Add the field definitions to your config files using the formats shown above.
