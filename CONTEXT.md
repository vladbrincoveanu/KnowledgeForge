# KnowledgeForge Domain Context

## Core Domain Terms

### C4 Model

The KnowledgeForge system extracts architecture following the [C4 model](https://c4model.com/):

- **System Context** (C4 Level 1): The entire software system under analysis — name, purpose, external dependencies, actors, languages, frameworks, and IT landscape metadata.
- **Container** (C4 Level 2): A deployable unit — a process, service, database, or frontend — that the system is composed of.
- **Component** (C4 Level 3): A grouping of related code elements (classes, functions) that provide a coherent public interface within a Container. Not internal implementation details.
- **Code** (C4 Level 4): Not currently implemented.

### Extraction Pipeline

- **Context Manager**: Orchestrates detection of system-level metadata (languages, frameworks, actors, external dependencies, IT landscape fields).
- **Container Manager**: Manages detection of deployable units — runs structure, Compose, Helm, Terraform, Kubernetes, and Python library detectors in sequence.
- **Component Extractor**: Extracts components from parsed source code using TreeSitter — not regex. Groups them via community detection.
- **LLM Enrichment**: Second-pass enrichment using an LLM to add descriptions and infer relationships.
- **Graph Writer**: Persists extracted C4 data to Neo4j.

### IT Landscape Fields

Extracted for every system:

- **domain**: Business area (e.g., "E-Commerce", "Infrastructure", "Analytics")
- **owner**: Team or squad responsible for the system
- **status**: Lifecycle stage — `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`
- **tier**: Criticality — `Tier 1 - Production Critical`, `Tier 2 - Production Standard`, `Tier 3 - Development/Internal`
- **data_class**: Data sensitivity — `General`, `Confidential`, `Restricted`, `Public`
- **active_experts**: Number of active contributors (bus factor proxy)
- **compliance**: Architectural risk assessment

### HITL (Human In The Loop)

When a field is extracted with confidence below 0.70, a **Review Item** is written to PostgreSQL. A reviewer can approve, reject, or override the value via the Review Dashboard. Fields with confidence ≥ 0.70 are accepted automatically.

### Review Item

A pending human review task persisted to PostgreSQL. Triggered when an extraction confidence falls below threshold. Contains: field name, candidate values, LLM suggestion, evidence, confidence score.

### Relationship Types

- **uses**: A Container or Component depends on another Container or external system
- **async**: Asynchronous communication via a message broker or topic
- **publishes-to**: A Container publishes to a topic/queue
- **subscribes-to**: A Container subscribes to a topic/queue

## Technology Detection

- **Language**: Programming language (Python, TypeScript, Go, Java, C#, etc.) detected via file extension and AST analysis
- **Framework**: Web framework detected from dependencies or source patterns (e.g., FastAPI, React, Spring Boot)
- **Technology**: Specific library or tool (e.g., "PostgreSQL", "Redis", "Kafka")

## Deployment

- **deployment**: How a Container is deployed — `Docker`, `Helm`, `Kubernetes`, `Terraform`, `Serverless`
- **runtime_environment**: Where it runs — `Kubernetes`, `AWS Lambda`, `Local`, `Docker`
- **protocol**: Communication protocol — `HTTP`, `HTTPS`, `gRPC`, `messaging`, `WebSocket`

## Extracted Data Storage

- **Neo4j**: Graph database storing extracted C4 model nodes (System, Container, Component) and relationships
- **PostgreSQL**: Stores Review Items for HITL workflow
- **JSON**: Bundled demo architecture, benchmark results
