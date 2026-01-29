# C4 Context Level - Extraction Guide

## What We Extract

The C4 Context level captures the **system boundary** and its **external relationships**. This includes:

1. **System Identity** - Name, purpose, type
2. **IT Landscape Metadata** - 7 operational fields
3. **External Dependencies** - Third-party services with URLs
4. **Actors** - Users and external systems interacting with the system

---

## System Identity

| Field | Source | Logic |
|-------|--------|-------|
| **name** | Repository name | Clean and format repo name |
| **purpose** | README.md | Extract description, first paragraph, or summary |
| **type** | Repository structure | Detect: application, library, infrastructure, documentation |

---

## IT Landscape Metadata (7 Fields)

### 1. Domain 🏢
**Business area or technical category**

Sources: Repository name, README.md, directory structure  
Patterns: `e-commerce`, `payment`, `infrastructure`, `data-platform`  
Default: `Infrastructure`

### 2. Owner Team 👥
**Team responsible for the codebase**

Priority chain:
1. Parse `CODEOWNERS` file → Extract team names like `@team-name`
2. Parse `README.md` → Look for "Owner:", "Team:", "Maintained by:"
3. Git contributors → Run `git shortlog -sn --all`, parse email domains

**Critical:** Requires full Git history (`--depth=999999`)

### 3. Lifecycle Status 🔄
**Current software lifecycle stage**

Logic:
- Check README.md badges: `[Deprecated]`, `[Active]`, `[Archived]`
- Analyze last commit date:
  - <6 months = `Production / Operational`
  - 6-18 months = `Maintenance Mode`
  - 18-36 months = `Legacy`
  - >36 months = `Deprecated / Frozen`

### 4. Criticality Tier ⚡
**Business impact and SLA requirements**

Sources: README.md keywords, directory structure  
Logic:
- `/prod/`, `/production/` → `Tier 1 - Mission Critical`
- `/staging/` → `Tier 2 - Business Important`
- `/dev/`, `/test/`, "demo", "sample" → `Tier 3 - Development/Internal`

### 5. Data Sensitivity 🔒
**Data classification and compliance**

Pattern matching:
- PII indicators: `password`, `email`, `ssn`, `credit_card`, `phone`, `address`
- Compliance: `GDPR`, `HIPAA`, `PCI`, `SOC2`
- Classification: `PII` if sensitive patterns found, else `Internal`

### 6. Active Experts (Bus Factor) 🚌
**Number of engineers with deep knowledge**

Calculate from `git shortlog -sn --all`:
- Top contributor >70% commits → Bus Factor: 1 (HIGH RISK)
- Top 2 contributors >80% commits → Bus Factor: 2
- Distributed contributions → Bus Factor: 3+
- No commits in last year → Bus Factor: 0 (frozen repo)

### 7. Architectural Compliance ✅
**How well code follows standards**

Checklist:
- ✅ README.md exists
- ✅ Tests directory present
- ✅ CI/CD configuration
- ✅ Architecture documentation
- ✅ No hardcoded secrets
- ✅ Clean directory structure

Scoring:
- 6-7 checks → `COMPLIANT`
- 3-5 checks → `AT_RISK`
- 0-2 checks → `NON_COMPLIANT`

---

## External Dependencies 🔗

**What:** Third-party services the system depends on  
**Types:** Cloud (AWS, Azure), Databases, Payment (Stripe), Auth (Auth0), APIs

### Detection Sources

| Source | Pattern | Example |
|--------|---------|---------|
| `values.yaml` | Any `https?://` URL | `stripe_api: https://api.stripe.com` |
| `.env` files | Environment variable URLs | `DATABASE_URL=https://db.cloud.com` |
| `docker-compose.yml` | Service image URLs | `image: postgres:14` |
| `Dockerfile` | External downloads | `RUN curl https://download.com/pkg` |
| `README.md` | Documented services | `Uses AWS S3: https://s3.amazonaws.com` |

### Service Recognition (15+ types)

| Pattern | Service Name | Type |
|---------|--------------|------|
| `stripe` | Stripe | payment |
| `aws`, `s3` | AWS S3 | cloud/storage |
| `postgres` | PostgreSQL | database |
| `redis` | Redis | cache |
| `mongodb` | MongoDB | database |
| `kafka` | Kafka | messaging |
| `elasticsearch` | Elasticsearch | search |
| `auth0` | Auth0 | authentication |
| `sendgrid` | SendGrid | email |

### Output Format
```json
{
  "name": "Stripe",
  "type": "payment",
  "url": "https://api.stripe.com",
  "detected_from": "values.yaml"
}
```

---

## Actors 👤

**What:** Users, administrators, or external systems that interact with the system

### Detection Sources
1. README.md sections: "Users", "Actors", "Personas"
2. Architecture diagrams: Parse C4 diagrams for actor definitions
3. Documentation: User guides, API docs mentioning user types

### Default Actors
If no explicit actors found, assume: `["User", "Administrator"]`

---

## Extraction Pipeline

```
GitHub Repository
    ↓
git clone --depth=999999 (full history)
    ↓
Parse Files:
  - README.md (purpose, owner, tier, dependencies)
  - CODEOWNERS (owner)
  - values.yaml, .env (external URLs)
  - Git history (owner, bus factor, status)
    ↓
Apply Pattern Matching:
  - Domain inference
  - Service type recognition
  - Compliance checks
    ↓
Output JSON:
{
  "system_context": {
    "name": "...",
    "purpose": "...",
    "type": "...",
    "domain": "...",
    "owner": "...",
    "status": "...",
    "tier": "...",
    "data_class": "...",
    "active_experts": 0,
    "compliance": "..."
  },
  "external_dependencies": [...],
  "actors": [...]
}
```

---

## Testing

```bash
# Run context extraction tests
make test-e2e

# Test specific fields
make test-owner        # Owner detection
make test-endpoints    # Endpoint extraction
```

All context extraction is covered by E2E tests: **11/11 passing** ✅

---

## Files

| File | Purpose |
|------|---------|
| `context_manager.py` | Orchestrates context extraction |
| `metadata_detector.py` | Detects IT landscape metadata |
| `dependency_detector.py` | Detects external dependencies |
| `github_downloader.py` | Clones repos with full history |
| `test_e2e_extraction.py` | E2E test suite |

---

## Key Insights

✅ **Full Git history required** - Owner detection needs `--depth=999999`  
✅ **Multi-source detection** - Checks 5+ files for each field  
✅ **Smart defaults** - Infers values when explicit data missing  
✅ **Pattern-based** - Uses regex + keyword matching  
✅ **URL extraction** - Automatic for external services  
✅ **Deduplication** - Removes duplicate external dependencies
