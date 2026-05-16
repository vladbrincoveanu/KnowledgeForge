---
name: c4-model-architecture
description: Apply the C4 model to visualize, document, and communicate software architecture. Use this skill when the user asks to create architecture diagrams, document a system's structure, produce C4 context/container/component/code diagrams, communicate system design to stakeholders, or reason about software boundaries and dependencies at any level of abstraction.
---

# C4 Model Architecture Skill

The C4 model is a lightweight, layered framework for visualizing and communicating software architecture at four levels of abstraction: Context, Containers, Components, and Code. The core idea is that a software system can be understood as a set of "maps" at varying levels of detail — analogous to zooming in from a city overview down to street level.

> **Source:** This skill is derived directly from the C4 book (O'Reilly Early Release, Chapters 1–9, authored by Simon Brown). All definitions, conventions, and examples are authoritative.

---

## What Software Architecture Diagrams Must Communicate

Architecture is "the significant decisions, where significance is measured by cost of change" (Grady Booch). Software architecture diagrams should communicate the outcome of decision-making across three themes:

| Theme | Examples |
|---|---|
| **Technology** | Programming languages, libraries, frameworks, target deployment environments |
| **Elements** | How software is decomposed into executable building blocks at different levels (monolith vs microservices, layers vs features); how data is stored and structured |
| **Relationships** | Dependencies and interactions between elements (synchronous vs asynchronous, data formats, protocols) |

Technology choices must appear on diagrams. "High-level logical diagrams without technology choices" is an anti-pattern rooted in pre-Agile waterfall separation of architect and developer roles — it is not appropriate for modern software teams.

---

## Core Principle: Audience-Driven Abstraction

Every C4 diagram must be designed for a specific audience. Before producing any diagram, determine:
- **Who is reading it?** (executive, architect, developer, product owner, operations)
- **What decision or understanding does it need to support?**
- **What level of technical detail is appropriate?**

| Level | Primary Audience | Scope |
|---|---|---|
| L1 System Context | Technical and non-technical, inside and outside the team | People + Systems |
| L2 Containers | Architects, engineers, DevOps, QA, compliance, product owners | Apps, Services, Stores |
| L3 Components | Architects, engineers, third-level support | Internal modules within a container |
| L4 Code | Engineers only | Classes, functions, interfaces |

---

## Canonical Vocabulary (Authoritative Definitions)

These definitions come directly from the C4 book. Use them precisely — imprecise use of these terms (e.g., calling a service a "component" when it is a "container") is the root cause of most diagramming ambiguity.

### Person
A human who uses or interacts with the software system. Model via **roles** (not individual names) — e.g., "Personal Banking Customer", "System Administrator", "Back Office Staff". Include functional users (people doing business tasks with the system) and optionally operational staff (admins with dedicated UI).

**Fields:** `name` (role name), `description` (what this role does with the system)
**Element label on diagram:** `[Person]`

### Software System
The highest level of abstraction. A software system is something that **delivers value to its users** (human or automated). It is typically:
- What a single software development team is **building, owns, and has responsibility for**
- Something whose internal implementation details are **visible to that team**
- Often corresponds to a single source code repository; anyone on the team may modify it
- Often deployed as a unit

Things that are **NOT** software systems: product domains, bounded contexts, business capabilities, feature teams, tribes, squads.

**Fields:** `name`, `description`
**Element label on diagram:** `[Software System]`

### Container
An application or data store that **needs to be running** for the overall software system to work. A container is a **runtime concept** — a boundary around code being executed or data being stored.

> ⚠️ "Container" in C4 does NOT mean Docker container. It means any separately deployable/runnable unit with a degree of isolation.

**Application containers include:**
- Server-side web application (Spring Boot, Rails, Express, Django, ASP.NET MVC, etc.)
- Client-side web application (React, Angular, Vue SPA running in a browser)
- Client-side desktop application (WPF, Electron, Swift/macOS, JavaFX)
- Mobile app (iOS, Android)
- Server-side console application (standalone `main()` process in Java, C#, Python, etc.)
- Serverless function (AWS Lambda, Azure Function)
- Shell script (Bash, Zsh)

**Data store containers include:**
- Database schema (relational: MySQL, PostgreSQL, SQL Server, Oracle; document: MongoDB; graph: Neo4j; NoSQL: Redis, Cassandra, Riak)
- Blob or content store (AWS S3 bucket, Azure Blob Storage container, CDN-hosted files)
- File system (local full file system, networked SAN/NAS portion)

**The critical isolation property:** Communication between containers requires **out-of-process/remote calls** across a process or network boundary. Components within the same container communicate via in-process method calls.

**Fields:** `name`, `technology` (runtime/framework/DB technology), `description` (responsibilities for apps; entities/tables/objects stored for data stores)
**Element label on diagram:** `[Container]` or specific shape per type

### Component
A **grouping of related functionality encapsulated behind a well-defined interface**, running inside a container. Components are **not separately deployable** — the container is the deployable unit; components run inside containers.

A component is essentially **a collection of code** — one level of abstraction above raw code elements:
- Java/C#/C++: a collection of classes, interfaces, enums
- C (procedural): a collection of files in a directory
- F#/Haskell (functional): a module — a logical grouping of related functions and types
- JavaScript: a module — objects and functions

**Fields:** `name` (domain-aligned, e.g., `OrderController`, `PaymentRepository`), `technology` (framework/library), `description` (responsibilities)
**Element label on diagram:** `[Component]`

### Code Element
Classes, interfaces, enums, functions, objects — the basic building blocks of whatever programming language is in use. This is the level of UML class diagrams.

---

## Diagram Types

### Static Structure Diagrams (the "C4" in C4)

The four hierarchical static structure diagrams form the core of the model. They show **what exists** — the structural elements and their relationships at rest.

#### Level 1: System Context Diagram

**Intent:** Show how the software system fits into the world around it — who uses it and what external systems it interacts with.

**Scope:** A single software system as a black box.

**Content:**
- The software system in scope (one box)
- People (actors, roles, personas) who use the system
- External software systems the system interacts with
- Labelled unidirectional relationships between all elements

**What NOT to include:** Internal containers, APIs, databases, protocols, infrastructure choices, any implementation detail.

**Relationships:** Plain-language labels indicating intent or data flow. Can be high-level — protocol details are not required at this level.

**Recommended?** Yes — for all engineering teams.

**Audience:** Everybody, technical and non-technical, inside and outside the engineering team.

**Questions it answers:**
- What is the software system we are building?
- Who is using it?
- What are users doing with it?
- How does it fit into the existing system landscape?

---

#### Level 2: Container Diagram

**Intent:** Zoom into the software system to show the applications and data stores (containers) inside it.

**Scope:** A single software system — show its internal containers plus the people and external systems from the system context diagram (repeat them for continuity).

**Content:**
- Software system boundary (shown as a **dotted rectangle** surrounding the containers)
- All containers inside the system boundary
- People and external software systems from the system context (repeated)
- Labelled unidirectional arrows between all elements, including technology/protocol

**Relationship annotation:** Each relationship should include:
1. `description` — what the source does to/with the destination (e.g., "reads data from", "makes API requests to")
2. `technology` — the primary protocol (e.g., `JSON/HTTPS`, `XML/HTTPS`, `SOAP/HTTPS`, `gRPC/TLS`, `JDBC`)
3. Optionally: solid line for synchronous, dashed line for asynchronous

**Container diagram should NOT contain:** Deployment details (Docker, Kubernetes, cloud infrastructure, load balancers, firewalls). Those belong in deployment diagrams.

**Recommended?** Yes — for all engineering teams.

**Audience:** Architects, engineers, DevOps/ops staff, QA, compliance teams, non-technical product owners (for change impact review).

**Questions it answers:**
- How has the software system been decomposed into applications and data stores?
- What are the responsibilities of those containers?
- What are the primary technology choices?
- How do containers communicate with each other?
- As an engineer, where do I write code to add a feature?

---

#### Level 3: Component Diagram

**Intent:** Zoom into a single container to show the components inside it.

**Scope:** A single container — one component diagram per container. Do not combine components from multiple containers on a single diagram.

**Content:**
- Container boundary (a box around the components)
- Optionally: the parent software system boundary (outer box)
- Components inside the container
- People, external software systems, and other containers from the container diagram (repeated)
- Labelled unidirectional arrows

**Relationship annotation:** Same as container diagrams. For component-to-component interactions that are in-process method calls, technology annotation is optional (no network boundary crossed).

**Recommended?** Optional. Do not create for: data store containers (document with ER diagrams instead), very simple microservices with a single purpose. Use for: larger applications with complex internal structure, components with non-obvious design, onboarding contexts.

**Audience:** Architects, engineers, third-level support.

**Warning on volatility:** Component diagrams age rapidly with code changes. Consider whether the benefit of maintaining them outweighs the cost. Component diagrams become cluttered quickly once there are more than a handful of components.

---

#### Level 4: Code Diagram

**Intent:** Zoom into a single component to show its internal code structure.

**Scope:** A single component. Use UML class diagram for OO languages (Java, C#, C++).

**Recommended?** Rarely. The code already exists as source of truth. Use only for: safety-critical systems, highly complex components requiring explanation, frameworks/libraries for external consumers.

**Practical approach:** Link to the source repository instead of maintaining a diagram. An annotation like "See GitHub repository: /backend/src/adapter" is lower-overhead and stays accurate.

---

### Supporting Diagrams

Three additional diagram types supplement the static structure.

#### Dynamic Diagram (Chapter 7)

**Intent:** Show how a subset of static elements collaborate at runtime to implement a specific feature, use case, or user story.

**Scope:** Variable — can show software systems collaborating (high abstraction) down to code elements collaborating (low abstraction). Constrain scope as tightly as possible. Do not mix abstraction levels.

**Two styles:**

| Style | Description | Best for |
|---|---|---|
| **Sequence diagram** (UML) | Elements as columns (left to right), timeline top to bottom, horizontal arrows showing interactions in order | Complex ordering, guard conditions, loops, precise sequencing |
| **Collaboration/communication diagram** | Free-form "boxes and arrows" with numbered arrows indicating interaction order | Simpler interactions, whiteboard-friendly, visually cleaner |

Both styles show the same information differently. The collaboration style is easier to draw and less visually cluttered.

**Elements on dynamic diagrams are instances** of elements from the static model. Reuse the same names exactly.

**Audience:** Mirrors the audience of the corresponding static diagram level (e.g., system-level flow → same audience as system context; component-level flow → same audience as component diagram).

**Recommended?** Yes, but **sparingly** — only for:
- Architecturally interesting or significant flows
- Recurring patterns illustrating an architectural style
- Features with complicated interactions that are easier to explain with a diagram than text

Do NOT create one per feature across 100 features. The maintenance cost is prohibitive.

**KnowledgeForge guidance:** Do not auto-extract dynamic diagrams. They require human curation to select which flows are architecturally significant. Offer as an on-demand generation feature: user specifies a scenario, KnowledgeForge traces the call path through the extracted graph.

---

#### Deployment Diagram (Chapter 8)

**Intent:** Show how instances of containers (and software systems) are deployed onto infrastructure in a given deployment environment.

**Scope:** A single software system in a single deployment environment. Draw separate diagrams per environment when environments differ structurally (dev, staging, production).

**Four element types:**

| Element | Definition |
|---|---|
| **Container instance** | An instance of a C4 container running in the environment |
| **Software system instance** | An instance of an external software system in the environment |
| **Deployment node** | Infrastructure that software is deployed INTO — physical servers, VMs, Docker hosts, K8s clusters, PaaS environments, JVM/app server runtimes, database server runtimes |
| **Infrastructure node** | Items/services USED BY the environment but not deployed into — DNS services, load balancers, routers, firewalls, CDNs |

Deployment nodes can **nest**: e.g., AWS eu-west-1 region > AWS Fargate > Docker container > Spring Boot application.

**Infrastructure vs Deployment node distinction:**
- A **deployment node** is something you deploy software INTO (EC2 instance, Docker host, K8s pod, JVM)
- An **infrastructure node** is something that routes or enables traffic (Cloudflare CDN, AWS Application Load Balancer, Route53 DNS)

**Recommended?** Yes — particularly for the live/production environment (critical for incident response).

**Audience:** Architects, engineers, operations and support staff.

**KnowledgeForge guidance:** Deployment topology is the one level NOT inferrable from source code. Requires IaC as a separate ingestion pipeline:

| IaC Source | What it reveals |
|---|---|
| `docker-compose.yml` | Local/dev topology, port mappings, service dependencies |
| Kubernetes manifests / Helm `values.yaml` | Cluster structure, namespace isolation, replica counts, ingress |
| Terraform / CDK | Cloud resource topology, region/AZ placement, managed service config |
| CI/CD pipeline files | Environment promotion, deployment targets |

Flag absent IaC explicitly in extraction output: "Deployment topology could not be extracted — no IaC source found."

---

#### System Landscape Diagram (Chapter 9)

**Intent:** A map of multiple software systems within a chosen scope — showing how all systems in a group, department, or organisation fit together.

**Scope:** Your choice. Common options:
- An organisation (only works for small organisations)
- A group or department
- A product domain
- A business capability
- A DDD bounded context

**Content:** People and software systems only — no container or component detail. Essentially a system context diagram without the focus on a single system.

**Motivation:** Most organisations lack a holistic view of their IT landscape. Diagramming it breaks down silos and enables impact analysis ("what breaks if this system is removed?", "what is the blast radius of a restructuring?").

**Recommended?** Yes, particularly for larger organisations. Make it interactive (double-click a system → navigate to its C4 diagrams) for maximum value.

**Audience:** Same as system context — technical and non-technical people, inside and outside the engineering team.

---

## Modelling Decision Rules

### The Core Question: Software System vs. Container?

From the book's canonical example (Internet Banking System with AWS SES and S3):

**AWS Simple Email Service → modelled as a Software System**
The Backend uses the SES API to send emails. SES is "just a service that we use — an external dependency." Provided the API is stable, you don't need to know how it works.

**AWS S3 bucket → modelled as a Container**
"The S3 bucket that we will create is a data store that's an integral part of our software system. We will have complete control and responsibility for what is stored inside that bucket — the objects, how they are organised, and the data format of each object. The S3 bucket is an integral part of our software system, despite being hosted elsewhere."

**Decision rule:** "Do you control its internals?"
- **Yes** → Container (even if hosted/operated externally — your S3 bucket, your RDS instance)
- **No** → Software System (external API you call; vendor controls the runtime)

### KnowledgeForge Ownership Classifier Signals

**Indicates Container (you own it):**
- Database connection strings pointing to your own hostnames
- Schema migration files in the repo (`/migrations`, Alembic, Flyway, Prisma)
- `Dockerfile` or `docker-compose.yml` service definition building/running it
- IaC resource defined in your Terraform/CDK (`aws_rds_instance`, `aws_s3_bucket`, `aws_elasticache_cluster`)
- Health check or monitoring config in your repo targeting this service
- The bucket/schema name is your team's naming convention

**Indicates Software System (external):**
- SDK import from a vendor package (`boto3`, `stripe`, `twilio`, `sendgrid`, `requests` + external URL)
- API key or webhook secret in environment variables (not connection strings to your infra)
- Base URL pointing to a public domain (`api.stripe.com`, `hooks.slack.com`, `email-smtp.amazonaws.com`)
- OAuth client credentials for a third-party identity provider
- No migration files or schema definitions for the datastore

### Component Granularity Decision

Extract a component when it has:
1. A distinct responsibility that could be named in a domain glossary
2. Relationships to other named components (not just internal function calls)
3. A lifecycle that could theoretically be isolated

Do NOT extract a component for:
- Utility/helper classes with no external relationships
- DTOs, value objects, thin wrappers
- Private methods — model the class, not its internals

### Person vs. Software System
A **Person** is a human role. A **Software System** is automated. If something is ambiguous:
- Human uses an admin panel → model the human as Person, the panel as a separate Software System
- Fully automated bot or scheduled job → Software System only

---

## Diagram Conventions (from the Book)

### Diagram titles
Use the pattern: `[Level] View: [System Name]`
- `System Context View: Internet Banking System`
- `Container View: Internet Banking System`
- `Component View: Backend — Internet Banking System`

### Element type labels
Every element on a diagram should display its type explicitly inside the box, to eliminate ambiguity:
- `[Person]`
- `[Software System]`
- `[Container]` or `[Web Application]`, `[Mobile App]`, `[Database]`, `[Message Broker]`, etc.
- `[Component]`

### Diagram key/legend
Every diagram MUST have an accompanying key/legend that explains:
- Shapes and what they represent
- Line styles (solid vs dashed, arrowhead styles)
- Color coding if used

A diagram without a key requires verbal explanation — diagrams must be able to stand alone.

### Relationship arrows
- Always unidirectional (from source to destination)
- Dashed line style (recommended default)
- Labelled with description + technology/protocol
- Solid lines for synchronous communication; dashed lines for asynchronous (optional convention but clear when used)

### Software system boundary
On container diagrams: draw a **dotted rectangle** around the containers to show the software system boundary explicitly.

### Container boundary
On component diagrams: draw a box around the components to show which container they belong to.

---

## Diagramming vs. Modelling

**Diagramming** = creating point-in-time visuals. Diagrams drift from reality as the system evolves. You end up explaining the gaps.

**Modelling** = building a single structured source of truth. Names, relationships, and metadata are defined once; diagrams are generated views of the model. Changes propagate automatically. The model can be queried ("which components depend on this service?").

For multi-team, long-lived systems: prefer modelling tools (Structurizr) over standalone drawing tools (draw.io, Miro). The upfront investment pays off with consistency, discoverability, and lower drift.

---

## C4 Diagram Quality Checklist

Before finalising any C4 diagram:

1. The diagram has a clear title using the `[Level] View: [System Name]` convention
2. A short description explains the diagram's purpose
3. All elements have explicit type labels (`[Person]`, `[Software System]`, `[Container]`, `[Component]`)
4. All objects have clear names — acronyms expanded, generic terms replaced
5. All relationships are labelled with intent/purpose
6. Relationships on container diagrams include the technology/protocol
7. A diagram key/legend is present and explains all notation
8. Shapes, line styles, colors are used consistently throughout
9. The diagram contains the right level of detail for its intended audience
10. The diagram can stand alone without verbal explanation

---

## Relationship and Metadata Reference

### Relationship fields (canonical)

| Field | Required | Notes |
|---|---|---|
| `source` | Yes | Name of the source element |
| `destination` | Yes | Name of the destination element |
| `description` | Yes | Plain-language label: what the source does to/with the destination |
| `technology` | Recommended at L2+ | Protocol or technology (REST, HTTPS, gRPC, JDBC, AMQP, Kafka, WebSocket, GraphQL) |
| `direction` | Implied | Unidirectional by default; bidirectional only when both sides initiate |

### Protocol detection — KnowledgeForge tree-sitter signals

| Protocol | Source code fingerprints |
|---|---|
| REST/HTTPS | `requests.get/post`, `fetch()`, `axios`, `HttpClient`, `@RestController`, OpenAPI spec |
| gRPC | `.proto` files, `grpc.Channel`, `stub.Method()`, protobuf imports |
| JDBC/SQL | `jdbc:postgresql://`, `jdbc:mysql://`, `SQLAlchemy`, `psycopg2`, `pg` driver |
| AMQP/RabbitMQ | `pika`, `amqplib`, `@RabbitListener`, `channel.basicPublish()` |
| Kafka | `KafkaProducer`, `KafkaConsumer`, `@KafkaListener`, `confluent_kafka` |
| WebSocket | `ws://`, `wss://`, `socket.io`, `WebSocket()`, `@ServerEndpoint` |
| GraphQL | `gql`, `Apollo Client`, `@GraphQLQuery`, `graphene`, `.graphql` schema files |
| S3/Blob | `boto3.client('s3')`, `BlobServiceClient`, `aws_s3_bucket` resource |
| SMTP | `smtplib`, `nodemailer`, `JavaMailSender`, `sendgrid` |
| XML/HTTPS | `JAXBContext`, `XmlSerializer`, `.xml` payloads with HTTPS clients |

Emit detected protocol as the `technology` field on the relationship. When multiple protocols are detected between the same pair, emit one relationship per protocol.

### Element metadata fields (canonical)

**Person:**
| Field | Notes |
|---|---|
| `name` | Role name, not individual name |
| `description` | What this role does with the system |

**Software System:**
| Field | Notes |
|---|---|
| `name` | System name |
| `description` | What it does; one sentence |
| `external` | Boolean — true if not owned by the team |

**Container:**
| Field | Notes |
|---|---|
| `name` | Meaningful name tied to responsibility |
| `technology` | Runtime, framework, or database technology |
| `description` | Plain-language responsibility statement |
| `domain` | Business subdomain this container belongs to |
| `owner` | Team or individual responsible (from git history) |
| `status` | `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` |
| `tier` | `Tier 1`, `Tier 2`, `Tier 3`, `Unknown` |
| `data_class` | `PII`, `Credit-Card`, `Internal`, `Public`, `Unknown` |

**Component:**
| Field | Notes |
|---|---|
| `name` | Domain-aligned name (`OrderController`, `PaymentRepository`) |
| `technology` | Language/framework if relevant |
| `description` | Responsibility in plain language |
| `container` | Parent container name |

**Deployment Node:**
| Field | Notes |
|---|---|
| `name` | Infrastructure resource name |
| `technology` | Cloud provider + service (AWS Fargate, K8s Node, Docker host, JVM) |
| `environment` | `Production`, `Staging`, `Development` |
| `parent` | Parent node name if nested |
| `node_type` | `deployment` (software deployed into it) or `infrastructure` (routes/enables traffic) |

### Tag conventions

| Tag | Meaning |
|---|---|
| `external` | Software systems not owned by the team |
| `database` | Any container that stores data |
| `message-broker` | Any container that routes async messages |
| `frontend` | Browser or mobile apps |
| `gateway` | API gateways, BFFs, load balancers |
| `deprecated` | Elements planned for removal |
| `pii` | Containers or systems that handle personally identifiable information |
| `serverless` | AWS Lambda, Azure Function, etc. |
| `blob-store` | S3 buckets, Azure Blob, CDN content |

---

## What C4 Is Not

The C4 model does not replace all other diagram types. Use supplementary diagrams where appropriate:
- UML activity diagrams → business processes and workflows
- UML state charts → state machines
- UML class diagrams → domain models
- Entity relationship diagrams → relational data models
- ArchiMate → enterprise architecture layers

C4 works well for custom-built, bespoke software systems in general-purpose languages. It is **less suited** to: embedded systems/firmware, heavy-customisation platforms (SAP, Salesforce), libraries/frameworks/SDKs (UML is often better here).

---

## Example: Internet Banking System (from the Book)

### Context Level
- **Personal Banking Customer** `[Person]` — views account balances, makes payments online
- **Internet Banking System** `[Software System]` — the system being built
- **Core Banking System** `[Software System]` — existing off-the-shelf bank product; manages all banking data; provides XML/HTTPS API
- **Amazon Web Services Simple Email Service** `[Software System]` — external email delivery service; used for MFA, fraud alerts, notifications

### Container Level
- **Single-Page Application** `[Container: JavaScript/Angular]` — provides Internet banking functionality via web browser
- **Static Content** `[Container: Directory]` — delivers the SPA; can be served via nginx or CDN depending on environment
- **Backend** `[Container: Java/Spring Boot]` — provides JSON/HTTPS API to the SPA; authenticates users; makes XML/HTTPS calls to Core Banking System; uses SES for email
- **Database** `[Container: MySQL Schema]` — stores user registration information, hashed authentication credentials
- **Statement Store** `[Container: AWS S3 Bucket]` — stores cached PDF bank statements (owned by this team — modelled as container, not software system)

> **Ownership rule demonstrated:** AWS Simple Email Service = Software System (external API, you don't control internals). AWS S3 Statement Store = Container (your team owns what's in it, defines the schema, controls the objects).

### Component Level (Backend container)
- **Sign In API** `[Component: Spring MVC]` — handles sign in requests from the SPA
- **Security Component** `[Component: Spring Bean]` — validates credentials against the database; issues session tokens; triggers MFA emails
- **Email Component** `[Component: Spring Bean]` — sends emails via SES
- **Accounts Summary API** `[Component: Spring MVC]` — handles account listing requests; delegates to Core Banking System Adapter
- **Statement API** `[Component: Spring MVC]` — handles statement requests; uses Statement Component
- **Statement Component** `[Component: Spring Bean]` — retrieves cached statements from Statement Store; generates new ones from Core Banking System
- **Core Banking System Adapter** `[Component: Spring Bean]` — abstracts XML/HTTPS communication with the Core Banking System

### Deployment (Development Environment)
- Bank WAN `[Deployment Node]`
  - Developer Laptop: Windows or macOS `[Deployment Node]`
    - JVM `[Deployment Node]` → Backend instance
    - Web Browser `[Deployment Node]` → SPA instance
    - Docker `[Deployment Node]` → nginx → Static Content instance
    - Docker `[Deployment Node]` → MySQL → Database instance
    - Docker `[Deployment Node]` → MinIO → Statement Store instance (S3-compatible)
    - Mock SES `[Deployment Node: Docker]` → logs emails, no real delivery
  - corebanking-dev server `[Deployment Node: Bank Data Center]` → Core Banking System instance

### Deployment (Live Environment)
- Customer's Computer `[Deployment Node]` → Web Browser → SPA instance
- Cloudflare `[Infrastructure Node]` → CDN proxy to S3 (ib.bigbank.com DNS CNAME)
- AWS eu-west-1 `[Deployment Node]`
  - AWS S3 `[Deployment Node]` → Static Content instance
  - AWS Application Load Balancer `[Infrastructure Node]` → routes to Fargate
  - AWS Fargate `[Deployment Node]` → Docker `[Deployment Node]` → Backend instance (multiple replicas)
  - AWS RDS `[Deployment Node]` → MySQL → Database instance
  - AWS S3 `[Deployment Node]` → Statement Store instance
  - AWS SES `[Software System Instance]` → real email delivery
  - AWS Direct Connect `[Infrastructure Node]` → private network to bank data center
- Bank Data Center `[Deployment Node]`
  - corebanking-live server `[Deployment Node]` → Core Banking System instance
