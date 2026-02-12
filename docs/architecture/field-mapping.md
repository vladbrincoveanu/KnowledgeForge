# KnowledgeForge — Context-Level Field Reference

**Version:** 1.0
**Last Updated:** February 2026
**Source of truth for:** `app/domain/models/services.py` → `Service`

This document describes all 18 fields extracted at the **C4 Context Level** — one entry per microservice discovered in a repository.

---

## Quick Reference Table

| # | Field | Type | Required | Detection Method | New in v1? |
|---|-------|------|----------|-----------------|------------|
| 1 | `name` | `str` | ✅ | Directory name / manifest name | No |
| 2 | `description` | `str` | — | LLM from README + route handlers | No |
| 3 | `owner` | `str` | — | CODEOWNERS → git blame → CI env vars → UNKNOWN | Improved |
| 4 | `owner_detection_source` | `str` | — | Records which fallback step found the owner | **New** |
| 5 | `languages` | `List[str]` | — | File extension counts + shebang lines + `.csproj` TFM | Improved (was `language`) |
| 6 | `frameworks` | `List[Dict]` | — | Config files parsed for name+version | Improved (was `framework`) |
| 7 | `status` | `ServiceStatus` enum | — | Git activity windows (30/90/180 days) | Improved |
| 8 | `tier` | `ServiceTier` enum | — | SLA markers + monitoring configs + README keywords | No |
| 9 | `data_class` | `str` | — | PII/PCI/legal regex patterns | No |
| 10 | `domain` | `str` | — | LLM classification (free-text) | No |
| 11 | `business_domain` | `BusinessDomain` enum | — | Keyword taxonomy + LLM fallback → fixed 10-domain list | **New** |
| 12 | `compliance_score` | `int` (0-100) | — | 7-check weighted rubric | **New** |
| 13 | `compliance_confidence` | `float` | — | Confidence in the compliance assessment | **New** |
| 14 | `api_surface_types` | `List[APISurfaceType]` | — | Route decorators, `.proto` files, GraphQL schemas, CLI parsers | **New** |
| 15 | `deployment_targets` | `List[DeploymentTarget]` | — | Dockerfile, K8s manifests, serverless.yml, Terraform, Procfile | **New** |
| 16 | `documentation_quality` | `int` (0-100) | — | 6-check rubric (README, OpenAPI, inline docs, ADRs, CHANGELOG, examples) | **New** |
| 17 | `inter_service_comms` | `List[Dict]` | — | HTTP client calls, gRPC channels, queue producer/consumer patterns | **New** |
| 18 | `bus_factor` | `float` (1.0-10.0) | — | Active experts × (1 − Gini coefficient), scaled 1-10 | **New** |

---

## Field Details

### 1. `name`
- **Type:** `str`
- **Source:** Directory name, then README `# Title`, then `package.json/.csproj` name field
- **Example:** `"payment-service"`

### 2. `description`
- **Type:** `str`
- **Source:** LLM call using README + top-level route handlers + `__main__` entrypoints
- **Prompt focus:** What business problem does this service solve?
- **Fallback:** README first paragraph if LLM unavailable
- **Example:** `"Handles payment processing via Stripe and stores transaction records in PostgreSQL"`

### 3. `owner`
- **Type:** `str`
- **Source (4-step fallback chain):**
  1. `CODEOWNERS` file — first pattern matching the repo root
  2. `git blame` — top committer over last 90 days (email)
  3. CI config env vars — `SLACK_CHANNEL`, `TEAM_NAME`, `OWNER` in GitHub Actions / Jenkinsfile / GitLab CI / CircleCI
  4. `"UNKNOWN"` if all steps fail
- **Example:** `"payments-squad"` or `"alice@acme.com"`

### 4. `owner_detection_source`
- **Type:** `str`
- **Values:** `"CODEOWNERS"`, `"git_blame"`, `"ci_config"`, `"UNKNOWN"`
- **Purpose:** Audit trail for owner confidence

### 5. `languages`
- **Type:** `List[str]`
- **Source:** File extension counting + shebang line parsing; `.csproj` `<TargetFramework>` element; `Directory.Build.props` fallback
- **Example:** `["Python", "TypeScript"]` or `["C#"]`

### 6. `frameworks`
- **Type:** `List[Dict[str, str]]`  — shape: `[{"name": "FastAPI", "version": "0.104.1"}]`
- **Source:** `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, NuGet `.csproj` packages
- **Example:** `[{"name": "FastAPI", "version": "0.104.1"}, {"name": "SQLAlchemy", "version": "2.0"}]`

### 7. `status`
- **Type:** `ServiceStatus` enum
- **Values:**

| Value | Condition |
|-------|-----------|
| `ACTIVE` | ≥1 commit in the last 30 days |
| `MAINTENANCE` | Commits in 90d window but not 30d |
| `DEPRECATED` | Commits in 180d window but not 90d |
| `ARCHIVED` | No commits in the last 180 days |

### 8. `tier`
- **Type:** `ServiceTier` enum — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- **Source:** SLA annotations in README, monitoring config keywords (`pagerduty`, `sla`, `critical`)

### 9. `data_class`
- **Type:** `str` — `"PII"`, `"PCI"`, `"PHI"`, `"CONFIDENTIAL"`, `"PUBLIC"`
- **Source:** Regex scan for sensitive field names, GDPR/PCI keywords

### 10. `domain`
- **Type:** `str` (free-text, LLM output)
- **Purpose:** Legacy field; prefer `business_domain` for filtering

### 11. `business_domain`
- **Type:** `BusinessDomain` enum
- **Values:** `Payments`, `Identity`, `Logistics`, `Commerce`, `Analytics`, `Infrastructure`, `Communication`, `Data`, `Security`, `Other`
- **Detection:** Keyword matching first; LLM fallback for ambiguous cases
- **Extensible:** Pass `extra_domains=["Healthcare", "Legal"]` to `BusinessDomainClassifier`

### 12. `compliance_score` + 13. `compliance_confidence`
- **Type:** `int` (0-100) + `float`
- **7-check rubric (configurable weights):**

| Check | Default Weight | Signal |
|-------|---------------|--------|
| CI/CD | 20% | `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `.circleci/` |
| Tests | 20% | `tests/`, `spec/`, `test_*.py`, `*.test.ts` directories |
| Security scanning | 15% | `trivy`, `snyk`, `bandit`, `semgrep` in CI config |
| No secrets | 15% | `.gitignore` containing `.env`; absence of hardcoded tokens |
| README | 10% | `README.md` with >200 characters |
| Dependencies | 10% | `requirements.txt`, `package.json`, `go.mod` present |
| Structure | 10% | Recognizable directory layout |

- **Tiers:** EXCELLENT (≥80), COMPLIANT (≥60), AT_RISK (≥40), NON_COMPLIANT (<40)
- **Risk overrides:** sensitive data class + no owner → forced NON_COMPLIANT; sensitive + ARCHIVED → minimum AT_RISK

### 14. `api_surface_types`
- **Type:** `List[APISurfaceType]`
- **Values:** `REST`, `GraphQL`, `gRPC`, `CLI`, `WebSocket`, `Event-Driven`, `None`
- **Detection signals:**

| Type | Signal |
|------|--------|
| REST | `@app.route`, `@router.get/post`, `app.use()`, Spring `@GetMapping` |
| GraphQL | `graphql`, `schema.gql`, `*.graphql`, Apollo setup |
| gRPC | `*.proto` files, `grpc.Channel`, `grpc.insecure_channel` |
| CLI | `click`, `argparse`, `cobra`, `clap` imports |
| WebSocket | `websocket`, `socket.io`, `ws://` patterns |
| Event-Driven | Kafka, RabbitMQ, SQS, EventBridge producer/consumer code |

### 15. `deployment_targets`
- **Type:** `List[DeploymentTarget]`
- **Values:** `Container`, `Kubernetes`, `Serverless`, `VM`, `Bare-Metal`, `PaaS`, `Unknown`
- **Detection files:**

| Target | Files |
|--------|-------|
| Container | `Dockerfile`, `docker-compose.yml` |
| Kubernetes | `*.yaml` with `kind: Deployment/Service`, `Chart.yaml` in root or `helm/` |
| Serverless | `serverless.yml`, AWS SAM template, `*.tf` with `aws_lambda_function` |
| VM | `Vagrantfile`, Ansible playbooks |
| Bare-Metal | `supervisord.conf`, `systemd/*.service` |
| PaaS | `Procfile`, `app.yaml` (GCP), `fly.toml` |

### 16. `documentation_quality`
- **Type:** `int` (0-100)
- **6-check rubric:**

| Check | Points | Signal |
|-------|--------|--------|
| README depth | 25 | >500 words, multiple sections |
| OpenAPI/Swagger spec | 20 | `openapi.yaml`, `swagger.json`, FastAPI `/docs` auto-generation |
| Inline documentation | 20 | Docstring / comment ratio in source files |
| ADRs | 15 | `docs/adr/`, `decisions/`, `*.adr.md` |
| CHANGELOG | 10 | `CHANGELOG.md`, `CHANGELOG.rst`, `HISTORY.md` |
| Examples | 10 | `examples/`, `notebooks/`, `scripts/` directories |

- **Tiers:** EXCELLENT (≥75), ADEQUATE (≥45), POOR (<45)

### 17. `inter_service_comms`
- **Type:** `List[Dict]`  — shape: `[{"target": "user-service", "protocol": "HTTP", "direction": "OUTBOUND"}]`
- **Detection patterns:**

| Protocol | Library Signals |
|----------|----------------|
| HTTP | `requests.get/post`, `httpx.Client`, `axios`, `fetch`, env var URL references |
| gRPC | `grpc.insecure_channel`, `grpc.secure_channel` |
| Kafka | `kafka-python`, `confluent-kafka`, `KafkaProducer/Consumer` |
| RabbitMQ | `pika`, `amqp://` connection strings |
| SQS/SNS | `boto3.client('sqs')`, `boto3.client('sns')` |

### 18. `bus_factor`
- **Type:** `float` (1.0–10.0) — higher is better (lower bus risk)
- **Formula:**
  1. Count `active_experts` = contributors with ≥5 commits in last 90 days
  2. Compute Gini coefficient `g` over commit frequency distribution
  3. `raw = active_experts × (1 − g)`
  4. `bus_factor = clamp(round(raw × 2 + 1), 1, 10)`
- **Interpretation:** Score 1 = single point of failure; Score 10 = knowledge widely distributed

---

## Enum Reference

```python
# app/domain/models/services.py

class ServiceStatus(str, Enum):
    ACTIVE      = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    DEPRECATED  = "DEPRECATED"
    ARCHIVED    = "ARCHIVED"

class ServiceTier(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"

class APISurfaceType(str, Enum):
    REST         = "REST"
    GRAPHQL      = "GraphQL"
    GRPC         = "gRPC"
    CLI          = "CLI"
    WEBSOCKET    = "WebSocket"
    EVENT_DRIVEN = "Event-Driven"
    NONE         = "None"

class DeploymentTarget(str, Enum):
    CONTAINER  = "Container"
    KUBERNETES = "Kubernetes"
    SERVERLESS = "Serverless"
    VM         = "VM"
    BARE_METAL = "Bare-Metal"
    PAAS       = "PaaS"
    UNKNOWN    = "Unknown"

class BusinessDomain(str, Enum):
    PAYMENTS        = "Payments"
    IDENTITY        = "Identity"
    LOGISTICS       = "Logistics"
    COMMERCE        = "Commerce"
    ANALYTICS       = "Analytics"
    INFRASTRUCTURE  = "Infrastructure"
    COMMUNICATION   = "Communication"
    DATA            = "Data"
    SECURITY        = "Security"
    OTHER           = "Other"

class CommDirection(str, Enum):
    INBOUND  = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BOTH     = "BOTH"
```

---

## Deferred Fields (Container Level)

These were considered for context level but deferred:

| Field | Reason |
|-------|--------|
| `service_version` | More meaningful at container level where per-deployment versions exist |
| `sla_target` | Requires runtime data not available from static analysis |
| `on_call_rotation` | Requires integration with PagerDuty / OpsGenie APIs |

---

## Migration Notes

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `language: str` | `languages: List[str]` | List, not single value |
| `framework: str` | `frameworks: List[Dict]` | Includes version numbers |
| `active_experts: int` | `bus_factor: float` | Gini-adjusted score, not raw count |
| `compliance_tier: str` | `compliance_score: int` + `compliance_confidence: float` | Numeric score added |
