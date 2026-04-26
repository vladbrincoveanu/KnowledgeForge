---
name: c4-model-architecture
description: Apply the C4 model to visualize, document, and communicate software architecture. Use this skill when the user asks to create architecture diagrams, document a system's structure, produce C4 context/container/component/code diagrams, communicate system design to stakeholders, or reason about software boundaries and dependencies at any level of abstraction.
---

# C4 Model Architecture Skill

The C4 model is a lightweight, layered framework for visualizing and communicating software architecture at four levels of abstraction: Context, Containers, Components, and Code. The core idea is that a software system can be understood as a set of "maps," each offering a different level of detail — analogous to zooming in from a city overview down to street level.

The four levels are not always all required. Most systems need Context and Containers. Components are used selectively for complex areas. Code is rarely needed and should be reserved for critical, safety-regulated, or onboarding-heavy contexts.

---

## Core Principle: Audience-Driven Abstraction

Every C4 diagram must be designed for a specific audience. Before producing any diagram, determine:
- **Who is reading it?** (executive, architect, developer, product owner)
- **What decision or understanding does it need to support?**
- **What level of technical detail is appropriate?**

| Level | Primary Audience | Scope |
|---|---|---|
| L1 Context | Business, Product, Architects, Developers | People + Systems |
| L2 Container | Product, Architects, Developers | Apps, Services, Stores |
| L3 Component | Architects, Developers | Internal modules within a container |
| L4 Code | Architects, Developers | Classes, functions, interfaces |

---

## Level 1: System Context

### What it is
The system context diagram treats the software system as a single black box placed within its environment. The focus is entirely on external relationships — not internal structure.

### What to include
- **People (actors):** End users, customers, operators, or any human role interacting with the system.
- **Software systems:** External platforms the system integrates with (payment gateways, notification services, CRMs, legacy systems, SaaS).
- **The system itself:** One box representing the software being described.

### What NOT to include
- Internal containers, APIs, or databases (these belong at L2)
- Protocols, infrastructure choices, or technical implementation details
- Internal logic of any kind

### Relationships
Label all arrows to indicate intent or data flow. Keep language plain — avoid jargon. Example: "sends push notifications to", "use for payment", "gather user data from".

### When this level is most valuable
- Executive presentations and strategic planning
- Evaluating new third-party integrations
- Onboarding new team members to the system's scope
- Aligning business and technical stakeholders before diving into design

### Common pitfalls
- Mixing internal containers into the context level (APIs, databases, services that are internals)
- Adding excessive technical detail (protocols, infrastructure)
- Inconsistent naming of the same actor across the diagram (e.g., alternating "Customer" and "End User")

### Best practice
Keep the diagram simple and readable. Label relationships clearly. Treat it as a communication tool first — its strength is aligning diverse stakeholders around a shared view of the system's place in its environment.

---

## Level 2: Containers

### What it is
A container diagram zooms into a single system to show its major runtime building blocks — the applications, services, and data stores that make up the system. Each container is a **separately deployable and/or runnable unit** with its own responsibilities.

> **Critical distinction:** A "container" in C4 is NOT a Docker container. It means "something that contains code or data." It's any unit you can independently deploy, scale, and operate — a web app, mobile app, microservice, database, message broker, or external SaaS dependency.

### What to include
- Web applications and mobile apps
- Backend services and APIs
- Databases and data stores (annotated with technology)
- Message brokers, queues, event buses
- External SaaS systems the system integrates with (even though you don't own them, they affect availability and team responsibilities)

### Defining the container boundary
Use deployability as your boundary test: if you can run it in its own process, VM, runtime environment, or managed service, it qualifies as a container. This prevents modeling at the wrong level of abstraction.

### How to annotate containers
Every container should include:
1. **Name:** Clear, meaningful name tied to what it does
2. **Technology:** The runtime or framework (Node.js, DynamoDB, PostgreSQL, etc.)
3. **Responsibility:** A short plain-language description of what the container does — accessible to non-technical readers (e.g., "Provides the products catalog", "Stores order details", "Processes payments")

Avoid purely technical labels like "Service A" or "DB1".

### Databases as first-class citizens
In C4, databases are containers. They require deployment, scaling, and operational decisions. Model them explicitly and annotate them with their technology and purpose. This surfaces architectural trade-offs (NoSQL vs relational, streams vs queues) that carry real design significance.

### Grouping by subdomain or team
Group containers into logical subdomains or bounded contexts (e.g., Catalog subdomain, Checkout subdomain, Fulfilment). Map these groups to team ownership. This makes the team-to-architecture relationship explicit and supports practices like Team Topologies and Conway's Law alignment.

### What this level makes explicit
- How responsibilities are distributed across the system
- How containers interact with each other and with external systems
- Which architectural trade-offs have been made (e.g., event-driven vs synchronous, relational vs document stores)
- Which teams own which parts of the system

### When this level is most valuable
- Architects and senior engineers reasoning about system boundaries, ownership, scalability, resilience, and compliance
- Developers new to the system who need a map of where responsibilities lie
- Product owners and technical stakeholders understanding how external services connect and how the team structure maps to capabilities

### Common pitfalls
- Oversimplifying (only two or three boxes when the system has many distinct runtimes)
- Overcomplicating (turning the diagram into a wiring map with too many implementation details)
- Omitting external SaaS dependencies — these affect availability and team responsibilities just as much as internal containers

---

## Level 3: Components

### What it is
A component diagram zooms inside a single container to show the major building blocks (modules, controllers, services, repositories, adapters) that collaborate to fulfill that container's responsibilities.

A component is defined by its **responsibility and boundaries**, not its technical implementation. In practice a component may map to a module, a class, or a cohesive set of functions — the key is that it represents a coherent unit of behavior within the container.

### When to use it
Not every container needs a component diagram. Use it selectively:
- Complex or business-critical services where multiple workflows interact in subtle ways (e.g., order management with validation, payment, shipping)
- Services with non-obvious internal structure (e.g., authentication: credential storage, token generation, MFA, auditing)
- Areas where misunderstanding the internal design would have significant downstream cost
- Onboarding scenarios where internal complexity must be explained quickly
- Situations where architectural trade-offs at the module level need to be made visible

Skip it for simple services where the container-level description is already sufficient.

### What to include
- Named components with clear, domain-aligned names (e.g., `OrderController`, `CatalogService`, `ProductRepository`, `PersonalizationClient`)
- The responsibility of each component in plain language
- Relationships between components showing how they collaborate
- Dependencies on external containers (databases, external systems)

### Naming conventions
Align component names with domain concepts. Names like `ProductRepository` or `CatalogService` are intuitive for both technical and business audiences. Avoid purely technical names like `Handler1` or `UtilityClass`.

### What to avoid
- Mapping every class or function — this is not a class diagram
- Crowding too many components into a single view — split into sub-diagrams if a service is large
- Treating these as exact mirrors of the codebase — they are guides to design intent, not documentation of implementation

### When to supplement
For deeper technical precision, reference the source repository directly rather than trying to capture all code-level detail in the diagram. An annotation like "See /checkout-service in the repository" keeps the reference alive without maintenance overhead.

### Audiences
Primarily developers and architects. Product owners and non-technical stakeholders typically do not need this level.

---

## Level 4: Code

### What it is
The code level diagram zooms into a single component to show the internal structure of classes, interfaces, methods, or functions. At this point the diagram resembles a UML class diagram or package view.

### When to use it
Rarely. The code level is appropriate for:
- Safety-critical or highly regulated systems that demand precise documentation
- Onboarding situations where internal complexity of a component must be explained quickly
- Documenting frameworks or libraries for external consumers
- Design reviews for highly complex components

In most cases, developers prefer to consult the source code directly. Keeping these diagrams in sync with rapidly evolving codebases is costly.

### Practical approach
Rather than producing detailed static code diagrams, link directly to the source repository. An annotation like "See GitHub repository: /checkout-service" keeps the reference lightweight and trustworthy without creating a maintenance burden.

### Audiences
Architects and senior developers only.

---

## Diagramming vs. Modelling

This distinction matters for long-lived, multi-team systems:

**Diagramming** produces a visual in the moment. It explains an idea well initially, but as the system evolves, the diagram diverges from reality. You end up explaining the gaps rather than the architecture.

**Modelling** builds a single source of truth — a structured representation of systems, containers, components, and their relationships. Changes made once propagate automatically across all diagrams. The model can be queried (e.g., "which components depend on this service?"). It supports consistency at scale.

When applying C4 at team scale, prefer modelling tools over standalone diagramming tools. The upfront investment in defining names, metadata, and structure pays off with consistency, discoverability, and lower drift.

---

## C4 Diagram Quality Checklist

Before finalizing any C4 diagram, verify:

1. The diagram has a clear and descriptive name
2. A short description explains what the diagram represents and its purpose
3. All objects are named clearly, with acronyms expanded or explained
4. Object responsibilities are self-explanatory or supported by displayed descriptions
5. Relationships (connections) are labeled to indicate intent or flow
6. Notation and symbols are explained, ideally through a legend
7. Shapes, line styles, borders, arrowheads, icons, and colors are used consistently and meaningfully
8. Object sizes are appropriate and proportional to their importance or hierarchy
9. The diagram shows the right level of detail for the intended audience
10. The intended audience can understand the diagram without additional explanation

---

## Best Practices Summary

**Start with Context and Containers.** These two levels cover most stakeholder needs and establish the foundation for all deeper design work.

**Invest in intention before drawing.** Understand your audience, the decisions they need to make, and what the diagram needs to communicate. Without this clarity, diagrams drift toward decoration.

**Use consistent naming and notation.** Define conventions for naming systems, containers, and components. Consistent labels, colors, and symbols reduce ambiguity and cognitive load across diagrams.

**Treat diagrams as living documents.** Architecture evolves. Update diagrams to reflect major changes. Don't spend excessive time perfecting diagrams that will change — prefer lightweight currency over elaborate stale documentation.

**Make trade-offs explicit.** The containers level in particular is where architectural decisions become visible — which services are separated, which databases are chosen, how events flow. Use the diagram to surface these decisions, not just describe the system.

**Align architecture to team ownership.** Mapping containers to teams and subdomains makes Conway's Law work for you rather than against you. Explicit ownership clarifies responsibility and reduces coordination costs.

**Code level is optional.** Many mature systems stop at the component level and rely on source repositories for code-level detail. Reserve code diagrams for where they genuinely reduce misunderstanding.

---

## Example: C4 Applied to an E-Commerce System

### Context Level
System: E-Commerce Platform
External actors and systems:
- New Customer (Actor) — browses and purchases products
- Salesforce (External System) — user management and notifications
- Twilio (External System) — push notifications
- Adyen (External System) — payment processing
- CMS SaaS / Contentful (External System) — product catalogue management
- Legacy Fulfilment System (System) — shipping and order processing (in-progress migration)
- Legacy E-Commerce (System) — unmigrated parts of the business

### Container Level (Catalog Subdomain)
- **Catalog MFE** — Node.js frontend app; renders product catalog in browser
- **Catalog Backend** — Node.js BFF-style API; retrieves products via JSON/HTTPS
- **Catalog Database** — NoSQL / DynamoDB; stores product metadata, media references
- **Catalog Metadata Backend** — microservice; syncs product data from CMS SaaS into the database and forwards to personalization

### Container Level (Checkout Subdomain)
- **Checkout MFE** — Node.js frontend; checkout UI, orchestrates backend and payment
- **Checkout Backend** — Node.js API; handles order placement via HTTPS
- **Payment Backend** — Node.js microservice; abstracts Adyen integration, persists receipts
- **Orders Database** — DynamoDB with Streams; stores order details, emits changes for fulfilment
- **Payments Database** — DynamoDB; stores receipt IDs, dates, amounts

### Component Level (Catalog Backend)
- **CatalogController** — handles incoming API requests from the Catalog MFE
- **CatalogService** — orchestrates requests: delegates to repository and personalization client, applies business rules, shapes responses
- **ProductRepository** — provides access to product data from Catalog Database
- **PersonalizationClient** — integrates with external Personalization SaaS

---

## Applying C4 to Infrastructure and Platform Systems

The C4 model applies equally well to infrastructure platforms, ML platforms, and multi-tenant systems — not just application software.

For a multi-tenant ML inference platform, the mapping might look like:

**Context Level:** Tenants (startup/SME actors), external identity provider, the AI Factory platform itself, upstream model registries or HPC schedulers as external systems.

**Container Level:** API Gateway, Inference Engine (vLLM), Model Store, Tenant Auth Service, Observability Stack, Job Scheduler Interface — each as independently deployable containers annotated with their technology and responsibility.

**Component Level (e.g., API Gateway container):** Rate Limiter, Consumer Auth Component, Route Handler, Metering Component, Token Counter — each with a defined responsibility and clear relationship to other components.

This layered approach makes multi-tenant boundaries, per-tenant access control flows, and cross-cutting observability concerns communicable to different stakeholder groups without a single diagram trying to capture everything at once.
