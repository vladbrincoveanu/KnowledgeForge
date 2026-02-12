Task 0 — Setup. Build test corpus (20 repos with ground truth), write accuracy scorer, record baseline, prep schema. Everything depends on this.
Task 1 — Fix Owner/Team. Build 4-step fallback chain: CODEOWNERS → git blame → CI config → "UNKNOWN". Add detection_source to output. Target: 0% blanks.
Task 2 — Add API Surface Type. New field. Scan code for REST routes, GraphQL schemas, gRPC protos, CLI entrypoints, WebSocket handlers. Multi-value. Target: ≥85% accuracy.
Task 3 — Improve System Purpose. Feed the LLM route handlers + entrypoints + CLI help, not just README. Descriptions should say what the service does, not what it is.
Task 4 — Upgrade Compliance Score. Add configurable weights (CI/CD=20, Tests=20, Security=15, etc). Output numeric 0-100 + tier + per-check breakdown with evidence.
Task 5 — Add Inter-Service Comms. Scan code for HTTP client calls and queue producer/consumer patterns. Surfaces runtime dependencies that package managers miss entirely.
Task 6 — Switch Business Domain. Replace free-text keyword matching with LLM classification into a fixed taxonomy (Payments, Identity, Logistics, etc). Configurable.
Task 7 — Split Languages & Frameworks. "Python" → languages. "FastAPI 0.104" → frameworks with version numbers.
Task 8 — Add Documentation Quality. Composite 0-100 score: README depth + OpenAPI spec + ADRs + inline docs + CHANGELOG + examples.
Task 9 — Remap Lifecycle Status. Replace vague labels with clear stages: Active → Maintenance → Deprecated → Archived. Based on git activity windows.
Task 10 — Add Deployment Target. Detect from Dockerfile, K8s manifests, serverless.yml, Terraform, Procfile. Multi-value.
Task 11 — Replace Active Experts with Bus Factor. Composite metric: expert count × (1 - Gini coefficient) × (1 + review spread). Scale 1-10.
Task 12 — Improve Actors. Add auth config scanning (OAuth, API keys, OpenAPI securitySchemes). Depends on Task 2 being done first.
Task 13 — Final Validation & Docs. Integration tests, migration script, FIELDS.md, CONFIGURATION.md, final before/after report.


C4 Context Level — Final Field Specification
KnowledgeForge • Pinned v1.0 • February 2026
This document is the single source of truth for which fields the C4 Context extraction layer will support, how each is detected, what changes are needed, and in what order.
 
1. Final Field Table — 18 Context-Level Fields
13 existing (5 keep, 7 improve, 1 merge) + 5 new = 18 total fields after merge.
#
Field
Status
Value
Effort
Detection Method
What Changes
1
System Name
✅ KEEP
High
—
Dir name → README title → package.json name
Nothing. Works well.
2
External Dependencies
✅ KEEP
High
—
Package managers (npm, pip, cargo, go.mod) + import scanning
Nothing. Core C4 entity, detection is strong.
3
Dep. Classification
✅ KEEP
High
—
LLM classifies each dep as BUSINESS or TECHNICAL
Nothing. Genuine differentiator, accuracy is good.
4
Criticality Tier
✅ KEEP
High
—
SLA markers in configs + monitoring configs + README keywords
Nothing. Directly drives prioritisation.
5
Data Classification
✅ KEEP
High
—
Regex patterns for PII, PCI, legal terms in code
Nothing. Expand regex library over time.
6
System Purpose
🔧 IMPROVE
High
Low
LLM analysis of README + route handlers + main entrypoints + CLI help strings
Add code-level scanning. README alone is often vague or missing. LLM prompt must include top-level route definitions and __main__ entrypoints.
7
Owner / Team
🔧 IMPROVE
High
Low
Fallback chain: CODEOWNERS → git blame (top committer last 90d) → CI/CD config (SLACK_CHANNEL, TEAM vars) → org chart API
Build 4-step fallback. Current implementation returns blank too often. Each step fires only if previous returns empty.
8
Languages
🔧 IMPROVE
Medium
Low
File extension counting + shebang lines
Split from Frameworks (was one field). Languages = stable identifier (Python, Go, Rust). Low-signal on its own but needed for filtering.
9
Frameworks + Versions
🔧 IMPROVE
High
Low
Config files (requirements.txt, package.json, go.mod, Cargo.toml) parsed for name + version
Split from Languages. "FastAPI 0.104" is actionable; "Python" is not. Extract version numbers wherever available.
10
Actors
🔧 IMPROVE
Medium
Medium
README analysis + OAuth scope definitions + API key middleware + OpenAPI securitySchemes + auth config files
Add auth config scanning. README-only detection is ~40% accurate. Auth configs raise it to ~75%.
11
Business Domain
🔧 IMPROVE
Medium
Low
LLM classifies into fixed taxonomy: [Payments, Identity, Logistics, Commerce, Analytics, Infrastructure, Communication, Data, Security, Other]
Replace free-text keyword matching with LLM + closed taxonomy. Customers can extend the taxonomy list.
12
Service Status
🔧 IMPROVE
Medium
Low
Git activity windows (30/90/180d) mapped to lifecycle enum
Map to explicit stages: ACTIVE (commits in 30d) → MAINTENANCE (commits in 90d, not 30d) → DEPRECATED (commits in 180d, not 90d) → ARCHIVED (no commits 180d+). Current labels are ambiguous.
13
Compliance Score
🔧 IMPROVE
High
Medium
7-check rubric with weighted scoring + configurable weights per customer
Add weights: CI/CD (20%) > Tests (20%) > Security scanning (15%) > No secrets (15%) > README (10%) > Dependencies (10%) > Structure (10%). Allow customers to override weights via config. Output both numeric score (0-100) and tier (COMPLIANT / AT_RISK / NON_COMPLIANT).
14
Bus Factor
⚠️ MERGED
Medium
Low
Composite: active expert count + commit Gini coefficient + review author spread
Replaces "Active Experts" (raw count). Single number 1-10 scale. Formula: experts × (1 - gini) × review_spread. Low score = high bus risk.
15
API Surface Type
🆕 ADD
High
Low
Scan for: FastAPI/Flask/Express route decorators (REST), graphql schema files (GraphQL), .proto files (gRPC), click/argparse (CLI), WebSocket handlers
New field. Enum: REST | GraphQL | gRPC | CLI | WebSocket | Event-Driven | None. Can be multi-value. Competitors require manual YAML for this.
16
Inter-Service Comms
🆕 ADD
High
Medium
Scan code for: HTTP client libs (requests, axios, fetch), queue producer/consumer patterns (Kafka, RabbitMQ, SQS), event bus topics, service mesh configs
New field. Discovers runtime dependencies that package managers miss. Output: list of {target_service, protocol, direction}. This IS the real dependency graph.
17
Documentation Quality
🆕 ADD
High
Low
Score: README word count (>500 = good) + OpenAPI/Swagger spec exists + ADR directory present + inline doc coverage (docstrings/comments ratio)
New field. 0-100 score. Goes far beyond "README exists" check in current compliance rubric. Major enterprise selling point.
18
Deployment Target
🆕 ADD
Medium
Medium
Dockerfile FROM line, K8s manifests, serverless.yml, Terraform provider blocks, docker-compose services, Procfile
New field. Enum: Container | Kubernetes | Serverless | VM | Bare-Metal | PaaS | Unknown. Answers "where does this run?" at context level without full infra integration.

 
2. Deferred to Container Level (Not in Context Scope)
Service Version — originally considered for context level, but version is more meaningful at container level where you can track per-deployment versions. Revisit when Container Detection (Phase 1 of roadmap) ships.
 
3. Implementation Sequence
Wave
Fields
Total Effort
Ship By
P0
 (Do First)
Owner/Team fallback chain
 API Surface Type
~3 days
Week 1
P1
 (High Impact)
Compliance Score (weighted)
 Inter-Service Comms
 Business Domain (LLM taxonomy)
~5 days
Week 2-3
P2
 (Polish)
Split Languages / Frameworks
 Documentation Quality
 Service Status → lifecycle enum
 Deployment Target
~5 days
Week 4-5
P3
 (Clean Up)
Bus Factor (merge Active Experts)
 Actors (auth scanning)
 System Purpose (code scanning)
~3 days
Week 6

 
4. Field Dependencies
·         Actors improvement depends on API Surface Type (P0) being done first — auth scanning needs to know the API type.
·         Inter-Service Comms uses External Dependencies as a starting point, then adds code-level scanning on top.
·         Documentation Quality replaces the README check inside Compliance Score — avoid double-counting.
·         Bus Factor replaces Active Experts — the old field is removed, not kept alongside.
·         Frameworks + Versions and Languages are a split of the current single field — migration needed in data model.
 
5. Success Metrics
·         Owner/Team blank rate drops from current ~35% to <10% after fallback chain.
·         API Surface Type detection accuracy >85% on test corpus of 50 repos.
·         Inter-Service Comms discovers >2x the dependencies vs. package-manager-only scanning.
·         Documentation Quality score correlates with manual documentation review (>0.7 Pearson).
·         Compliance Score weighted version shows clearer separation between healthy and unhealthy services.
·         Business Domain classification into fixed taxonomy achieves >80% agreement with manual labels.
 
6. Data Model Changes Summary
Change Type
Field
Details
SPLIT
Languages & Frameworks → Languages + Frameworks
One field becomes two. Languages: list[str]. Frameworks: list[{name: str, version: str}].
RENAME
Active Experts → Bus Factor
Type changes from int to float (1.0-10.0 scale). Old field removed.
ADD
API Surface Type
New field. Type: list[enum]. Values: REST, GraphQL, gRPC, CLI, WebSocket, Event-Driven, None.
ADD
Inter-Service Comms
New field. Type: list[{target: str, protocol: str, direction: enum[INBOUND|OUTBOUND]}].
ADD
Documentation Quality
New field. Type: int (0-100).
ADD
Deployment Target
New field. Type: list[enum]. Values: Container, Kubernetes, Serverless, VM, Bare-Metal, PaaS, Unknown.
MODIFY
Service Status
Type changes from str to enum. Values: ACTIVE, MAINTENANCE, DEPRECATED, ARCHIVED.
MODIFY
Compliance Score
Adds numeric_score: int (0-100) alongside existing tier. Adds weight_config: dict.
MODIFY
Business Domain
Type changes from str (free text) to enum (fixed taxonomy, extensible).
MODIFY
Owner / Team
Adds detection_source: str to track which fallback step found the owner.

 
7. Risks & Mitigations
·         LLM cost increase: System Purpose, Business Domain, and Actors all add LLM calls. Mitigate: batch prompts, cache results per commit SHA, set token limits.
·         Inter-Service Comms false positives: Code scanning for HTTP clients may flag test fixtures or dead code. Mitigate: require 2+ signals (import + usage in non-test file).
·         Taxonomy rigidity: Fixed Business Domain list may not fit all customers. Mitigate: allow customer-defined extensions appended to base list.
·         Migration complexity: Splitting Languages/Frameworks and renaming Active Experts requires data migration. Mitigate: run both old and new fields in parallel for 2 weeks, then cut over.

