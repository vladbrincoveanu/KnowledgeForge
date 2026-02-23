# C4 Context Level — Field & Logic Reference

> **Scope:** This document covers everything owned by the Context Level squad.
> **Iron Curtain:** Do NOT touch `sources/Api/app/services/c4/containers/` — that is the Container squad.

---

## Table of Contents

1. [File Map](#1-file-map)
2. [Orchestration — How the Pipeline Runs](#2-orchestration)
3. [The 7 Primary Fields](#3-the-7-primary-fields)
4. [Full Service Model](#4-full-service-model)
5. [Detection Logic by Field](#5-detection-logic-by-field)
6. [External Dependencies](#6-external-dependencies)
7. [Scoring Rubrics](#7-scoring-rubrics)
8. [Phase 8 Enhancement Chain](#8-phase-8-enhancement-chain)
9. [Data Flow Summary](#9-data-flow-summary)

---

## 1. File Map

```
sources/Api/app/services/c4/context/
├── context_manager.py        # Master orchestrator — calls all detectors
├── system_detector.py        # System name, purpose, languages, frameworks, actors, git metadata, URLs
├── dependency_detector.py    # External SaaS/database dependencies + freshness alerts
├── dependency_classifier.py  # LLM-powered or rule-based BUSINESS_SYSTEM vs TECHNICAL_INFRA
├── metadata_detector.py      # Owner, domain, tier, data_class, status, compliance, on_call_channel
└── example_usage.py          # End-to-end usage example

sources/Api/app/services/service_extraction/
├── service_enhancers.py               # Phase 8 — wires all specialist enhancers per service
├── compliance_scorer.py               # 7-check weighted compliance rubric
├── documentation_quality_scorer.py    # 6-check documentation scoring
├── inter_service_comm_detector.py     # Runtime HTTP/gRPC/queue call detection
├── auth_scanner.py                    # Auth mechanism detection
├── bus_factor_calculator.py           # Gini-weighted bus factor 1–10
├── api_surface_detector.py            # REST / GraphQL / gRPC / CLI / WebSocket / Event-Driven
├── deployment_target_detector.py      # Container / K8s / Serverless / VM / Bare-Metal / PaaS
└── business_domain_classifier.py      # Fixed taxonomy (Payments, Identity, Commerce, etc.)

sources/Api/app/domain/
├── services.py    # Service + ContextNode Pydantic models
└── entities.py    # Ontology / entity models
```

---

## 2. Orchestration

Entry point: `ContextManager.extract_context()` — runs **28 steps sequentially**.

| Step | Detector | What it does |
|------|----------|-------------|
| 1 | SystemDetector | Detect system name (package.json → pyproject.toml → README title → .sln → LLM) |
| 2 | SystemDetector | Generate 1-sentence system purpose (README → LLM) |
| 3 | SystemDetector | Detect environments (dev/staging/prod from values.yaml filenames) |
| 4 | SystemDetector | Detect app version (package.json → pyproject.toml → Chart.yaml) |
| 5 | SystemDetector | Detect tags (Helm Chart keywords and annotations) |
| 6 | SystemDetector | Detect OpenAPI/Swagger spec URL |
| 7 | SystemDetector | Detect documentation URL (Confluence, Notion, GitBook) |
| 8 | SystemDetector | Detect monitoring URL (Grafana, Datadog) |
| 9 | SystemDetector | Detect regulatory frameworks (SOC2, GDPR, HIPAA, PCI-DSS, ISO27001) |
| 10 | DependencyDetector | Detect external dependencies (package manifests, Helm, .env, Docker) |
| 11 | DependencyDetector | Detect dependency freshness alerts (unpinned, range, non-semver versions) |
| 12 | SystemDetector | Detect languages (by file extension frequency) |
| 13 | SystemDetector | Detect frameworks (from manifests and package.json) |
| 14 | SystemDetector | Detect context actors (user/system roles from README) |
| 15 | SystemDetector | Extract git metadata (branch, commit hash, dates, top contributors) |
| 16 | SystemDetector | Get repository root URL (git remote origin) |
| 17 | SystemDetector | Collect context sources (key files: README, Dockerfiles, K8s manifests) |
| 18 | MetadataDetector | Detect owner team (4-step fallback chain) |
| 19 | MetadataDetector | Infer business domain (scoring system across 9 domains) |
| 20 | MetadataDetector | Determine criticality tier (heuristic scoring) |
| 21 | MetadataDetector | Infer data classification (PII / Credit-Card / Legal / General) |
| 22 | MetadataDetector | Detect service status (git activity patterns) |
| 23 | MetadataDetector | Calculate active experts (contributors with ≥1 commit in 90d) |
| 24 | MetadataDetector | Get git activity metrics (commits by period, dates, contributor count) |
| 25 | MetadataDetector | Get owner contributor stats (top 5 contributors with commit counts) |
| 26 | MetadataDetector | Detect on-call channel (CI config env vars → README scan) |
| 27 | MetadataDetector | Assess compliance risk (deterministic 6-rule engine) |
| 28 | ContextManager | Generate LLM description (optional — only if LLM available) |

---

## 3. The 7 Primary Fields

These are the core ITIL/CMDB-style fields extracted for every service at context level.

| # | Field | Type | Values |
|---|-------|------|--------|
| 1 | `domain` | `Optional[str]` | Infrastructure, AI/ML Processing, Data Engineering, User Management, API Gateway, CMS/Content, Commerce, Notifications, Developer Tools, General |
| 2 | `owner` | `Optional[str]` | Team name, email, "Unassigned", or None |
| 3 | `status` | `ServiceStatus` enum | `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` |
| 4 | `tier` | `ServiceTier` enum | `Tier 1 - Production Critical`, `Tier 2 - Production Standard`, `Tier 3 - Development/Internal`, `unknown` |
| 5 | `data_class` | `Optional[str]` | `PII`, `Credit-Card`, `Legal/Security`, `General` |
| 6 | `active_experts` | `int` | Count of contributors with ≥1 commit in last 90 days |
| 7 | `compliance` | `Optional[str]` | `COMPLIANT`, `AT_RISK`, `NON_COMPLIANT`, `UNKNOWN` |

---

## 4. Full Service Model

All fields on the `Service` Pydantic model relevant to context level:

```python
class Service(BaseModel):
    id: str                              # Unique identifier
    name: str                            # Service/repo name
    display_name: Optional[str]

    # ── 7 Primary Fields ─────────────────────────────────────────────────
    domain: Optional[str]                # Business area (see §3)
    owner: Optional[str]                 # Team or person responsible
    owner_contributors: list[str]        # Top contributor emails
    owner_contributor_stats: list[dict]  # [{email, name, commit_count}]
    contributor_count: int               # Total unique contributors
    owner_detection_source: Optional[str]  # "CODEOWNERS", "readme", "git_blame", "llm"

    status: ServiceStatus                # ACTIVE | MAINTENANCE | DEPRECATED | ARCHIVED | unknown
    status_evidence: Optional[dict]      # {commits_30d, commits_90d, commits_180d,
                                         #  last_commit_date, days_since_last_commit}

    tier: ServiceTier                    # Tier 1 | Tier 2 | Tier 3 | unknown
    data_class: Optional[str]            # PII | Credit-Card | Legal/Security | General

    active_experts: int                  # Contributors active in last 90d
    bus_factor: Optional[float]          # 1–10 composite (experts × (1 - Gini))

    compliance: Optional[str]            # COMPLIANT | AT_RISK | NON_COMPLIANT | UNKNOWN
    compliance_score: Optional[int]      # 0–100 weighted score from 7-check rubric
    compliance_confidence: Optional[float]  # 0.0–1.0 (1.0 = fully deterministic)
    compliance_factors: list[str]        # Human-readable evidence list

    # ── Service Characteristics ──────────────────────────────────────────
    description: Optional[str]           # LLM-generated or README-extracted
    notes: Optional[str]
    languages: List[str]                 # e.g. ["Python", "TypeScript"]
    frameworks: List[Dict]               # [{language, framework, detected_from}]
    port: Optional[int]
    endpoints: list[str]                 # Detected API endpoints

    repository_url: Optional[str]
    file_path: Optional[str]
    docker_compose_service: Optional[str]

    dependencies: list[str]              # Service IDs this service depends on
    dependents: list[str]                # Service IDs that depend on this
    direct_depends: list[str]            # From static import analysis

    # ── Context-Level Enrichment Fields ──────────────────────────────────
    api_surface_types: List[str]         # REST | GraphQL | gRPC | CLI | WebSocket | Event-Driven
    inter_service_comms: List[Dict]      # [{target, protocol, direction}]
    documentation_quality: Optional[int] # 0–100 score
    deployment_targets: List[str]        # Container | Kubernetes | Serverless | VM | Bare-Metal | PaaS
    business_domain: Optional[str]       # From fixed taxonomy (Payments, Identity, Commerce, etc.)

    # ── Git Activity ─────────────────────────────────────────────────────
    last_commit_date: Optional[datetime]
    commit_count_30d: int                # Commits in last 30 days
    commit_count_90d: int                # Commits in last 90 days
    commit_count_180d: int               # Commits in last 180 days

    # ── Metadata ─────────────────────────────────────────────────────────
    on_call_channel: Optional[str]       # "#slack-channel" or "pagerduty:key"
    attributes: dict[str, Any]           # Arbitrary extra attributes
    confidence: float                    # Overall extraction confidence (0.0–1.0)
    extracted_at: datetime               # Timestamp of extraction
    source: str                          # "code_extraction" (default)
```

---

## 5. Detection Logic by Field

### 5.1 `domain` — Business Domain Inference

**Method:** `MetadataDetector.infer_business_domain()`
**Approach:** Scoring system — each indicator increments a category counter.

| Category | Signals & Weights |
|----------|------------------|
| `infrastructure` | +4 if "microservice/cna/cloud/k8s/infra" in repo name; +3 for K8s/Helm/Terraform in dirs; +2 in container names |
| `ai_ml` | +3 for ml/model/train/pipeline in dirs; +2 in container names; +2 in pyproject for TensorFlow/PyTorch |
| `data_engineering` | +3 for etl/warehouse/analytics/spark in dirs; +2 in container names |
| `user_management` | +3 for auth/login/permission/oauth/identity in dirs; +2 in container names |
| `api_gateway` | +3 for gateway/proxy/ingress/router in dirs; +2 in container names; +1 in pyproject |
| `cms_content` | +5 in repo name; +3 in dirs; +4 in README keywords |
| `commerce` | +5 in repo name; +3 in dirs; +4 in README keywords |
| `notifications` | +5 in repo name; +2 in README |
| `developer_tools` | +2 for ci/cd/build/jenkins/gitlab in dirs |

**Tie-break:** If both `infrastructure` and `commerce` are highest → Infrastructure wins.
**Fallback:** Returns `"General"` when no category reaches a meaningful score.

---

### 5.2 `owner` — Owner Team Detection

**Method:** `MetadataDetector.detect_owner_team()`
**Approach:** 4-step fallback chain (stops at first hit):

1. **CODEOWNERS file** — Scan for `@org/team` patterns
2. **README** — Search for lines containing "maintainer:", "owner:", "team:", "contact:", or a Slack `#channel`
3. **Top git contributors** — Return top-5 contributor emails/names by commit count
4. **LLM enrichment** *(optional)* — Suggest team name from contributor email domains

**`owner_detection_source`** records which step succeeded: `"CODEOWNERS"`, `"readme"`, `"git_blame"`, `"llm"`.
**Fallback value:** `"Unassigned"` if all steps fail.

---

### 5.3 `status` — Service Status

**Method:** `MetadataDetector.detect_service_status()`
**Approach:** Git commit activity patterns.

| Condition | Status |
|-----------|--------|
| `commits_30d ≥ 5` OR `commits_90d ≥ 10` | `ACTIVE` |
| `days_since_last_commit > 180` | `DEPRECATED` |
| `commits_180d > 0` (but not active threshold) | `MAINTENANCE` |
| No matching condition | `unknown` |

**Note:** `DEPRECATED` always overrides other signals. If last commit was >180 days ago it is deprecated regardless of older history.
**Fallback:** File modification timestamps when no git history is available.
**Evidence:** Always returns `status_evidence` dict with all commit counts and dates for auditability.

---

### 5.4 `tier` — Service Criticality

**Method:** `MetadataDetector.determine_criticality()`
**Approach:** Heuristic scoring — accumulate points from multiple indicators.

| Indicator | Points |
|-----------|--------|
| Container count ≥ 10 | +3 |
| Container count ≥ 5 | +2 |
| Container count ≥ 2 | +1 |
| Helm replicas ≥ 3 | +1 |
| Helm health checks defined | +1 |
| Helm resource limits defined | +1 |
| Prometheus/Grafana/alerts in values.yaml | +1 |
| .sln file OR ≥ 5 .csproj files | +2 |
| ≥ 2 .csproj files | +1 |
| README mentions SLA | +3 |
| README mentions "production" or "critical" | +2 |
| README mentions "Tier 1" | +3 |
| README mentions "Tier 2" | +1 |
| docker-compose restart policies present | +2 |
| CI/CD configuration present | +1 |

**Thresholds:**

| Score | Tier |
|-------|------|
| ≥ 7 | Tier 1 - Production Critical |
| ≥ 3 | Tier 2 - Production Standard |
| < 3 | Tier 3 - Development/Internal |

---

### 5.5 `data_class` — Data Classification

**Method:** `MetadataDetector.infer_data_classification()`
**Approach:** Keyword scanning across source files (`*.py`, `*.ts`, `*.js`, `*.cs`, `*.java`, `*.go`).

| Class | Keywords (case-insensitive) | Threshold |
|-------|-----------------------------|-----------|
| `Credit-Card` | payment, creditcard, credit_card, invoice, transaction, billing, stripe, paypal, checkout, order | ≥ 3 matches AND at least one of: creditcard / stripe / paypal |
| `PII` | email, phone, address, firstname, lastname, username, customer, profile, gdpr, ccpa, personaldata, personal_data | ≥ 3 matches |
| `Legal/Security` | compliance, audit, encryption, authorize, authenticate, permission, rbac, acl, security | ≥ 3 matches |
| `General` | Default fallback | — |

**Special rule:** Infrastructure-focused repos default to `"General"` to avoid false positives.

---

### 5.6 `active_experts` — Active Maintainers

**Method:** `MetadataDetector.calculate_active_experts()`
**Definition:** Count of unique contributors with ≥ 1 commit in the last 90 days.
**Aggregation:** Walks across multiple git roots (up to 50 child `.git` directories).
**Fallback:** Returns `None` if no git history is accessible.

---

### 5.7 `compliance` — Compliance Risk

**Method:** `MetadataDetector.assess_compliance_risk()`
**Approach:** Pure deterministic calculation — no LLM, no external calls. Runs after all other fields are populated.

**6 rules (each adds a weighted penalty):**

| Rule | Condition | Weight |
|------|-----------|--------|
| `sensitive_data_low_tier` | data_class is PII/Credit-Card/Legal AND tier is Tier 3 | 2.0 |
| `sensitive_data_no_owner` | data_class is PII/Credit-Card/Legal AND owner is "Unassigned"/None | 2.0 |
| `critical_service_no_owner` | tier is Tier 1 AND owner is "Unassigned"/None | 1.5 |
| `no_active_maintainers` | active_experts = 0 | 1.5 |
| `deprecated_with_sensitive_data` | status = DEPRECATED AND data_class is sensitive | 1.5 |
| `single_point_of_failure` | tier is Tier 1 AND active_experts = 1 | 1.0 |

**Risk score = sum of triggered rule weights**

| Risk Score | Result |
|------------|--------|
| ≥ 3.0 | `NON_COMPLIANT` |
| ≥ 1.5 | `AT_RISK` |
| < 1.5 | `COMPLIANT` |

`compliance_confidence` is always `1.0` because this is fully deterministic.

---

### 5.8 `on_call_channel` — On-Call Channel

**Method:** `MetadataDetector.detect_on_call_channel()`
**Approach:** Two-step search.

**Step 1 — CI config env vars** (`.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `.circleci/`):

| Env Var | Returns |
|---------|---------|
| `SLACK_CHANNEL` / `SLACK_ONCALL_CHANNEL` | `#channel-name` |
| `PAGERDUTY_SERVICE_KEY` / `PAGERDUTY_SERVICE_ID` | `pagerduty:key` |

**Step 2 — README scan** (first 4000 characters):

| Pattern | Returns |
|---------|---------|
| Slack channel regex: `#[a-z][a-z0-9_-]{2,}` (excluding "readme", "usage", "install", "api") | `#channel-name` |
| PagerDuty regex: `pagerduty[^\n]*?([A-Za-z0-9_-]{4,})` | `pagerduty:key` |

Returns `None` if nothing found.

---

### 5.9 `bus_factor` — Bus Factor Score

**Method:** `bus_factor_calculator.py`
**Formula:** `score = active_experts × (1 - gini_coefficient)`
- Gini coefficient measures commit concentration: 0 = perfectly even distribution, 1 = one person owns everything.
- Score is clipped to the range [1, 10].
- Returns `1` (maximum risk) when no git history is available.

---

## 6. External Dependencies

### Detection Sources

**File:** `dependency_detector.py`

| Source | What is extracted |
|--------|------------------|
| `pyproject.toml` | `[tool.poetry.dependencies]` and `[dependencies]` sections |
| `package.json` | `dependencies` + `devDependencies` |
| `Helm values.yaml` | Recursively scanned for external URLs |
| `.env` files | URL pattern `https?://[^\s"']+` |
| `Dockerfile` | Base images + URL references |
| `docker-compose.yml` | Service images |
| `README` / docs | Dependency name patterns |
| `.csproj` / NuGet | Package references via 80+ entry NuGet→service name mapping |

**Filtering:** Internal references are excluded — localhost, 127.*, 0.0.0.0, bare IPs, `$VAR` placeholders.
**Deduplication:** Dependencies are deduplicated by name before classification.

### Classification Logic

**File:** `dependency_classifier.py`
**Primary:** LLM-based (if LLM available).
**Fallback:** Rule-based pattern matching.

| Class | Rule Indicators |
|-------|-----------------|
| `TECHNICAL_INFRA` | Names: postgres, mysql, mongodb, redis, kafka, rabbitmq, s3, elasticsearch. Types: database, cache, messaging, search, storage, monitoring, error-tracking |
| `BUSINESS_SYSTEM` | Names: stripe, auth0, okta, twilio, sendgrid, salesforce, slack. Types: payment, authentication, sms, email, crm, analytics, notifications |
| `UNKNOWN` | Everything else |

**Output per dependency:**
```json
{
    "name": "Stripe",
    "type": "payment",
    "detected_from": "pyproject.toml",
    "dependency_type": "BUSINESS_SYSTEM",
    "classification_confidence": 0.95,
    "classification_reasoning": "External SaaS payment processor"
}
```

### Freshness Alerts

| Alert Type | Condition |
|------------|-----------|
| `unbounded_version` | Version is `*` or `latest` |
| `range_version` | Version uses `^`, `~`, `>`, `<` |
| `non_semver_reference` | `git+`, `http:`, `workspace:`, etc. |

---

## 7. Scoring Rubrics

### 7.1 Compliance Score (7-check, 0–100)

**File:** `compliance_scorer.py`

| Check | Weight | Evidence looked for |
|-------|--------|---------------------|
| CI/CD configured | 20 | `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `.circleci/` |
| Tests present | 20 | `test_*.py` files or `tests/` directory |
| Security scanning | 15 | `SECURITY.md` or `.github/security/` |
| No secrets committed | 15 | Absence of `.env*` files (passes if not found) |
| README documentation | 10 | `README.md` exists |
| Dependency management | 10 | `requirements.txt`, `pyproject.toml`, or `package.json` |
| Repository structure | 10 | `src/`, `services/`, or `app/` dirs, or `*/Dockerfile` present |

**Score thresholds:**

| Score | Result |
|-------|--------|
| ≥ 75 | `COMPLIANT` |
| ≥ 45 | `AT_RISK` |
| < 45 | `NON_COMPLIANT` |

**Risk overrides (independent of score):**
- Sensitive data (PII/CC/Legal) + no owner → force `NON_COMPLIANT`
- Sensitive data + `ARCHIVED` status → force `AT_RISK`

### 7.2 Documentation Quality Score (6-check, 0–100)

**File:** `documentation_quality_scorer.py`

| Check | Points | Evidence looked for |
|-------|--------|---------------------|
| README depth | 25 | README > 300 chars AND ≥ 3 sections (Installation, Usage, API, Contributing, etc.) |
| OpenAPI/Swagger spec | 20 | `openapi.yaml`, `swagger.json`, or `/docs` endpoint |
| Inline doc coverage | 20 | ≥ 30% of source files have docstrings or JSDoc |
| ADR directory | 15 | `docs/adr/` or `adr/` directory exists |
| CHANGELOG | 10 | `CHANGELOG.md` or `HISTORY.md` present |
| Examples | 10 | `examples/` or `samples/` directory present |

**Thresholds:**

| Score | Quality |
|-------|---------|
| ≥ 75 | EXCELLENT |
| ≥ 45 | ADEQUATE |
| < 45 | POOR |

---

## 8. Phase 8 Enhancement Chain

**File:** `service_enhancers.py`
Runs after service discovery. Enriches each `Service` object in place.

| Phase | Enhancer | What it adds |
|-------|----------|-------------|
| 1 | `enhance_with_git_status` | owner (4-step chain), status, commit metrics |
| 2 | `enhance_with_domain_detection` | domain from imports and directory structure |
| 3 | `enhance_with_dependencies` | cross-service dependencies from static import analysis |
| 4 | `enhance_with_descriptions` | LLM-generated description |
| 5 | `enhance_with_llm_enrichment` | Fill missing labels (domain, owner, tier, data_class) via LLM |
| 6 | `enhance_with_api_surface_types` | REST, GraphQL, gRPC, CLI, WebSocket, Event-Driven |
| 7 | `enhance_with_inter_service_comms` | Runtime service dependencies `[{target, protocol, direction}]` |
| 8 | `enhance_with_business_domain` | Fixed taxonomy classification |
| 9 | `enhance_with_documentation_quality` | 0–100 score |
| 10 | `enhance_with_deployment_targets` | Container, Kubernetes, Serverless, VM, Bare-Metal, PaaS |
| 11 | `enhance_with_bus_factor` | bus_factor (1–10) + active_experts count |

### API Surface Detection

**File:** `api_surface_detector.py`

| Surface | Detection signals |
|---------|------------------|
| REST | FastAPI, Express, Django, Flask, Spring Boot, ASP.NET Core route decorators |
| GraphQL | apollo-server, graphql-core, graphene, strawberry, Spring GraphQL |
| gRPC | grpc imports, `.proto` files, grpcio |
| CLI | argparse, click, typer, cobra, clap |
| WebSocket | socket.io, ws, websockets, SignalR |
| Event-Driven | Kafka, RabbitMQ, SNS/SQS producers/consumers |

### Inter-Service Communication Detection

**File:** `inter_service_comm_detector.py`

| Protocol | Detection patterns |
|----------|------------------|
| HTTP | requests, httpx, aiohttp, urllib, fetch, axios, Go `http.Get`/`Post`, Java `RestTemplate` |
| gRPC | `grpc.insecure_channel`, `grpc.secure_channel`, `grpc.dial` |
| Message Queue | `KafkaProducer`/`KafkaConsumer`, pika/RabbitMQ, SQS/SNS, Redis Pub/Sub |
| Env-var URLs | `os.getenv("*_URL")`, `os.getenv("*_HOST")`, `process.env.*_HOST` |

Output format: `{"target": "user-service", "protocol": "HTTP", "direction": "OUTBOUND"}`

### Auth Scanning

**File:** `auth_scanner.py`

| Auth Type | Detection signals |
|-----------|------------------|
| `OAuth2/OIDC` | oauth2, oidc, keycloak, okta, auth0 |
| `JWT` | jwt.decode, jwt.encode, PyJWT, jsonwebtoken |
| `APIKey` | api.?key, x-api-key, APIKey patterns |
| `BasicAuth` | BasicAuth, HTTPBasic, Authorization Basic |
| `SessionCookie` | flask_login, passport.session, express-session |
| `mTLS` | ssl_context, mutual.?tls, client.?cert |
| `None` | No auth detected |

Search sources: OpenAPI/Swagger `securitySchemes`, `.env` vars, source code imports, CI config.

**Special:** `auth_types` defaults to `["None"]` for empty directories (not an empty list).

### Deployment Target Detection

**File:** `deployment_target_detector.py`

| Target | Detection signals |
|--------|------------------|
| Container | `Dockerfile` present in repo |
| Kubernetes | K8s manifests (`*.yaml` with `apiVersion` + `kind`), `Helm Chart.yaml` |
| Serverless | Handler functions (AWS Lambda, Google Cloud Functions, Azure Functions) |
| VM | Vagrant, Packer, machine provisioning scripts |
| Bare-Metal | Ansible playbooks, direct server provisioning |
| PaaS | Heroku `Procfile`, `Cloud.yaml`, `app.json` |

---

## 9. Data Flow Summary

```
ContextManager.extract_context(repo_path)
    │
    ├─ SystemDetector          → name, purpose, languages, frameworks,
    │                            actors, git metadata, URLs, version, tags
    │
    ├─ DependencyDetector      → external_dependencies [{name, type, detected_from,
    │                            dependency_type, classification_confidence}]
    │                            dependency_freshness_alerts [{name, alert_type}]
    │
    ├─ MetadataDetector        → owner, owner_detection_source, domain,
    │                            tier, data_class, status, status_evidence,
    │                            active_experts, on_call_channel, compliance,
    │                            compliance_score, compliance_factors
    │
    └─ ContextManager (LLM)    → description (optional)

    ─── Output: dict with 50+ fields ───►  Neo4j storage

    ContextManager.build_context_relationships()
        │
        ├─ Actor → System edges
        └─ System → ExternalDependency edges
```

**Iron Curtain:** Context Manager outputs are consumed by the Container squad's pipeline as inputs. Context Manager does **not** call into `c4/containers/` code. Container detectors do **not** modify context-level fields.

---

## Key Heuristics & Edge Cases

| Topic | Rule |
|-------|------|
| Domain tie-break | If Infrastructure and Commerce both score highest → Infrastructure wins |
| Data class bias | Infrastructure repos default to `"General"` to prevent false PII positives |
| Status precedence | `DEPRECATED` (>180d since commit) always overrides other signals |
| Git aggregation | Multi-repo support: walks up to 50 child `.git` directories |
| Bus factor minimum | Returns `1` (maximum risk) when no git history exists |
| Active experts | Returns `None` (not 0) when git is unavailable — signals missing data vs. confirmed zero |
| Dependency dedup | Deduped by name before LLM classification is applied |
| Internal URL filter | Blocks localhost, 127.*, 0.0.0.0, `*`, `$VAR` placeholders, bare IPs |
| Compliance confidence | Always `1.0` — compliance assessment is fully deterministic, no ML |
| NuGet mapping | 80+ hardcoded entries mapping NuGet package names to external service names |
