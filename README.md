# KnowledgeForge

**The operating system for your software estate.**

KnowledgeForge is an automated architectural intelligence platform that transforms source code into a living, queryable map of your entire software landscape. From a single GitHub URL, it builds a C4-level graph — Context, Container, Component, Code — stored in Neo4j and surfaced through a React command center. No manual diagramming. No stale wikis. Just ground truth.

---

## The Problem We're Solving

Modern enterprises are flying blind.

- **$6T** in global tech debt, doubling since 2012 *(Protiviti)* — most of it invisible
- **30%** of IT budget wasted on misaligned projects due to structural failure of visibility *(PMI)*
- **$4.88M** average cost per data breach, with supply-chain risks unmanageable without a dependency map *(IBM)*
- **23–25%** annual engineering turnover exposing critical "bus factor" dependencies no one tracked

The root cause: **no ground-truth map of the software estate.** Architecture exists in Tribal Knowledge, hand-maintained diagrams that go stale day one, and EA tools disconnected from actual code. Every strategic decision — M&A, platform rationalization, security triage, succession planning — is made without a reliable map.

---

## Who It's For

| Persona | What They Get |
|---------|---------------|
| **CIO / CTO / Board** | Portfolio-level risk exposure, Key-Person Risk metrics, tech debt quantified in dollars, compliance blast-radius analysis |
| **Architect / Tech Lead** | Service dependency maps, blast-radius simulation before changes, API surface and deployment target inventory |
| **Platform / DevOps Engineer** | Auto-updating architecture as code evolves, ownership attribution from git history, external dependency tracking |
| **Developer / SRE** | Code-level internals with deep links back to Git, onboarding acceleration from months to hours |

---

## What KnowledgeForge Delivers

**Three altitudes. One source of truth.**

- **L1 — Ecosystem View**: Business capabilities, external integrations, vendor risks. For leadership and compliance teams.
- **L2 — Service View**: Microservices, containers, databases, message queues. For architects and tech leads planning changes.
- **L3 — Internals View**: Classes, functions, execution paths. For developers and SREs debugging or onboarding.

**How it works — the pipeline:**

```
Ingest  →  Parse  →  Model  →  Store  →  Serve
Webhook-driven  Tree-sitter AST  C4 ontology  Neo4j graph  3 views, zero manual input
Git repos       + LLM intent    Context/      Relationships  L1/L2/L3
Multi-language  Cross-file      Container/     as first-class  navigation
Zero config     dependencies     Component/Code  citizens
```

**Key capabilities:**

- Deterministic AST analysis via Tree-sitter — not heuristic scraping
- C4 ontology: domain, owner (from git history), status, tier, data_class, active_experts, compliance score
- External dependency classification: BUSINESS_SYSTEM vs TECHNICAL_INFRA
- Compliance scoring: 7-check rubric (CI/CD, security, docs, auth, monitoring)
- Doc quality scoring: 6-check ADRs and README depth rubric
- Inter-service communication pattern detection: HTTP, Queue, gRPC
- Bus factor / Key-Person Risk via betweenness centrality on the graph
- LLM-powered natural language queries across the architecture

---

## Business Outcomes

- Reduce **onboarding time** from months to hours with code-level architecture maps
- Quantify **true architectural debt** — coupling patterns and bottlenecks, not just line counts
- **M&A readiness**: expose duplicate billing, auth, and CRM stacks in post-acquisition portfolios
- **Security triage in minutes, not days**: trace CVE lineage through the graph to exact business systems exposed
- **Eliminate documentation debt**: the map is always current because it derives from code


---

## Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, SCSS, ReactFlow, Lucide React |
| **Backend** | FastAPI, Python 3.11, Pydantic V2 |
| **Graph Store** | Neo4j |
| **Metadata Store** | PostgreSQL |
| **Container** | Docker Compose |

## Quick Start (Docker)

```bash
make up
```

Services:
- **UI**: http://localhost:3000
- **API + docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (`neo4j` / `password`)

Stop:
```bash
make down
```

## Local Development

### API

```bash
cd sources/Api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### UI

```bash
cd sources/UI
npm install
npm run dev
```

## Extraction & C4 Context

System context extraction includes:
- `domain`, `owner` (from git history), `status`, `tier`, `data_class`, `active_experts`, `compliance`
- External dependencies: `values.yaml`, `README`, `.env`, `docker-compose`
- Actors: users and administrators

External dependencies are classified as `BUSINESS_SYSTEM` vs `TECHNICAL_INFRA` for C4 context/container separation.

## GitHub Scanning

Set `GITHUB_TOKEN` in `.env` for higher rate limits (5,000/hr) during org scans.

## Workspace Separation

- `sources/Api/app/services/c4/context/` — **our workspace** (Context level extraction)
- `sources/Api/app/services/c4/containers/` — owned by another developer (Container level)

## Testing

After any changes, run:

```bash
make quick-check    # Fast restart + tests (~1–2 min)
make full-check     # Complete rebuild + tests (~5–10 min)
```

For backend tests:
```bash
docker compose exec api python -m pytest tests/ -v
```

For frontend tests:
```bash
cd sources/UI && npm run test
```

## Contributing

The extraction pipeline is orchestrated by `ServiceExtractionPipeline` in `sources/Api/app/services/service_extraction/`. Key files:

- `service_enhancers.py` — 8-phase enhancement chain (compliance, docs, comms, auth, etc.)
- `context_manager.py` — Context extraction orchestrator
- `metadata_detector.py` — Compliance, doc quality, bus factor, on-call channel detection

Service status canonical values: `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` — not legacy strings like "Active-Dev".
