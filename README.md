# KnowledgeForge

**The operating system for your software estate.**

KnowledgeForge is an automated architectural intelligence platform that transforms source code into a living, queryable map of your entire software landscape. From a single GitHub URL, it builds a C4-level graph — Context, Container, Component, Code — stored in Neo4j and surfaced through a React command center. No manual diagramming. No stale wikis. Just ground truth.

Where traditional Enterprise Architecture tools ask humans to describe the system and hope reality catches up, KnowledgeForge inverts the model: **the code is the source of truth, and the architecture is derived from it, continuously, and at zero marginal cost.** Every commit updates the map. Every merge refreshes the risk profile. Every repository added expands the enterprise view without a single diagram being drawn by hand.

---

## Why This Matters — The Value We Add to the World

Software is now the primary substrate of every modern business — banks, hospitals, governments, retailers, airlines. Yet the people accountable for that software routinely operate without a reliable map of what they own, who wrote it, what it depends on, or what would break if it changed. The result is a trillion-dollar blind spot that shows up as missed acquisitions, preventable outages, failed audits, and talent that walks out the door carrying knowledge no one else has.

KnowledgeForge exists to **close that blind spot permanently.** By turning every codebase into a navigable graph of facts, it gives executives, architects, and engineers the same shared picture of reality — expressed at the altitude each of them needs. Leadership sees portfolios. Architects see services. Engineers see functions. And all three views are derived from the same underlying truth, extracted deterministically from the code itself.

The value we add is not another dashboard. It is the **elimination of an entire category of organizational ignorance** — the kind that compounds silently until it shows up as an incident, a lawsuit, a failed migration, or a missed quarter.

---

## The Problem We're Solving

Modern enterprises are flying blind.

- **$6T** in global tech debt, doubling since 2012 *(Protiviti)* — most of it invisible
- **30%** of IT budget wasted on misaligned projects due to structural failure of visibility *(PMI)*
- **$4.88M** average cost per data breach, with supply-chain risks unmanageable without a dependency map *(IBM)*
- **23–25%** annual engineering turnover exposing critical "bus factor" dependencies no one tracked
- **60%+** of post-merger IT integrations miss their synergy targets, primarily because neither side had an accurate inventory of the other's systems *(McKinsey)*
- **6–9 months** — the typical onboarding ramp for a senior engineer joining a mature codebase, most of it spent rediscovering decisions that were already made

The root cause: **no ground-truth map of the software estate.** Architecture exists in tribal knowledge, hand-maintained diagrams that go stale day one, and EA tools disconnected from actual code. Every strategic decision — M&A, platform rationalization, security triage, succession planning — is made without a reliable map.

This is not a tooling gap. It is a **knowledge gap with strategic consequences.** When the CIO cannot answer "which of our systems touch customer PII?" in minutes, compliance becomes theater. When an architect cannot see who depends on the payments service before deprecating it, outages become inevitable. When a new engineer cannot trace a request from the login page to the database, onboarding becomes attrition. KnowledgeForge attacks the root of all of these problems simultaneously, because they all stem from the same missing artifact: a trustworthy, continuously-updated map.

---

## Who It's For

| Persona | What They Get | Decision It Unblocks |
|---------|---------------|----------------------|
| **CIO / CTO / Board** | Portfolio-level risk exposure, Key-Person Risk metrics, tech debt quantified in dollars, compliance blast-radius analysis | "Where should I invest, rationalize, or divest next quarter?" |
| **M&A / Corporate Dev** | Target-company system inventory, duplication overlap with acquirer, integration-cost estimates grounded in real dependencies | "What am I actually buying, and what will it cost to integrate?" |
| **CISO / Security** | Blast-radius of any CVE traced through service edges to exposed business systems and data classes | "If this library is compromised, which customers and regulators do we notify?" |
| **Architect / Tech Lead** | Service dependency maps, blast-radius simulation before changes, API surface and deployment target inventory | "Can I safely deprecate this service, and who do I need to talk to?" |
| **Platform / DevOps Engineer** | Auto-updating architecture as code evolves, ownership attribution from git history, external dependency tracking | "Who owns this, where does it run, and what breaks if I touch it?" |
| **Engineering Manager** | Bus-factor heatmaps, owner concentration, onboarding-readiness scores per service | "Which teams are one resignation away from a crisis?" |
| **Developer / SRE** | Code-level internals with deep links back to Git, onboarding acceleration from months to hours | "How does a request actually flow through this system, end to end?" |
| **Compliance / Audit** | Continuously-evidenced compliance posture: CI/CD gates, auth checks, doc quality, data-class tagging | "Can I prove to the auditor that these controls exist — today, not last quarter?" |

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
- **Reduce change-failure rate** by simulating blast-radius before a deploy rather than discovering it in production
- **Protect institutional knowledge** by surfacing Key-Person Risk before the resignation email, not after
- **Shorten audit cycles** with machine-evidenced compliance signals that replace screenshot-based attestations
- **Unlock rationalization savings** by identifying redundant services, duplicate vendor integrations, and zombie repositories that still cost money

---

## Quantifying the Business Value

The value KnowledgeForge creates is not theoretical — it is directly tied to line items on the P&L and categories on the risk register. Below is how the capabilities translate into measurable outcomes.

| Value Lever | Mechanism | Typical Order-of-Magnitude Impact |
|-------------|-----------|-----------------------------------|
| **Engineering productivity** | Onboarding ramps collapse from 6–9 months to days; architects stop re-deriving the same diagrams | 10–20% recoverable capacity in a 500-engineer org |
| **Incident reduction** | Blast-radius analysis before merge; ownership and on-call surfaced automatically | 20–40% fewer change-induced incidents; lower MTTR via instant ownership lookup |
| **Security response** | CVE-to-service-to-data-class traceability in one graph query | Days-to-minutes reduction in exposure assessment; lower breach cost ($4.88M avg) |
| **M&A integration** | Pre-close system inventory; post-close duplication map | 10–30% reduction in integration cost; faster synergy realization |
| **Tech-debt rationalization** | Coupling/centrality metrics identify true bottlenecks; zombie services flagged | 5–15% infrastructure cost reduction; multi-year modernization prioritized by evidence |
| **Audit & compliance** | Continuous control evidence across the estate | Audit prep cycles shortened; reduced external audit fees; lower regulatory risk |
| **Talent risk** | Bus factor and expert-concentration surfaced as first-class metrics | Retention interventions before departures; succession planning grounded in data |

In aggregate, organizations of meaningful size typically leave **tens of millions of dollars per year** on the table because they cannot answer basic questions about their own software. KnowledgeForge is designed to make those answers a query away.

---

## Principles That Make the Value Real

The business value above is only achievable because of a set of engineering principles we hold non-negotiable.

**Deterministic over heuristic.** Core extraction uses Tree-sitter AST parsing, not regex or pattern-matching. LLMs augment the graph (naming, intent, summaries) but never replace the structural spine. This is why the output is auditable.

**Code is the source of truth.** Humans edit code, not diagrams. By deriving architecture from the repository, the map updates when reality updates. There is no drift, because there is no separate artifact to drift from.

**Three altitudes, one graph.** Context, Container, Component, and Code are not four disconnected products — they are four projections of the same underlying graph. A board member and a backend engineer can click through from one to the other without switching tools or losing context.

**Ownership is evidence, not opinion.** Owners are inferred from git history, not org charts, because org charts lie and commits don't. Bus factor and expert concentration are computed from the same signal.

**Compliance is continuous, not ceremonial.** Signals like CI/CD gates, auth presence, secret hygiene, and doc depth are extracted per service on every refresh, producing an always-current posture instead of a quarterly PDF.

**The graph is open.** The output is a standard Neo4j graph. Customers can query it, extend it, and integrate it with their existing tooling — no lock-in, no proprietary query language, no black box.

---

## The Bigger Picture — What We're Building Toward

KnowledgeForge is the first layer of a larger thesis: that **software organizations should be run on evidence, not folklore.** Today, the most consequential decisions in technology — what to build, what to retire, who to hire, what to acquire, what to defend — are made with whiteboards, spreadsheets, and the memory of whichever senior engineer happens to be in the meeting. That is not sustainable at the scale software now operates.

In the same way that accounting gave executives a reliable view of the financial estate, and CRM gave them a reliable view of the customer estate, KnowledgeForge is building the reliable view of the **software estate** — the substrate on which every other system now runs. The long-term outcome we are working toward is simple: **no strategic technology decision ever again made without a ground-truth map underneath it.**

That is the value we are adding to the world.

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
