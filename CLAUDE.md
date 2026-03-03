## Agent Team: Container Extraction

### Architect
- Owns design decisions for the container detection pipeline
- Evaluates whether detection phases correctly map to C4 Container semantics 
  (name, type/responsibility, technology, inter-container communication)
- Reviews extraction output against Simon Brown's container definition:
  "an application or data store that needs to be running for the system to work"
- Decides how to handle edge cases (e.g., sidecar containers, init containers, 
  shared volumes, multi-stage Dockerfiles)
- Produces specs and interface contracts, does NOT write implementation

### Implementer
- Writes extraction code for the assigned detection phase
- Each task scoped to one phase: Dockerfile parsing, docker-compose, Helm, or Terraform
- Runs tests before marking done
- Follows merge/dedup contract defined by Architect

### Reviewer  
- Reviews implementation against C4 container spec completeness
- Checks: does the extracted Container Dictionary capture name, type, 
  technology, and relationships?
- Validates edge cases against real repos (train-ticket, eShop, Robot Shop)
- Challenges Architect if extraction logic misclassifies 
  (e.g., init container treated as real container)
```

## Example Prompt to Launch
```
Create an agent team for KnowledgeForge container extraction:

- Architect: review the current 4-phase container detection pipeline 
  (Structure → Compose → Helm → Terraform → merge/dedup) and produce 
  a spec for handling inter-container relationships. C4 containers must 
  capture name, type, technology, and how they communicate.

- Implementer: implement the relationship extraction based on 
  Architect's spec — docker-compose links/networks, Helm service 
  dependencies, Terraform resource references.

- Reviewer: validate extracted container dictionaries against the 
  train-ticket repo (41 microservices). Check completeness and 
  flag any misclassified containers.

Architect finishes spec first. Then Implementer and Reviewer 
can work in parallel (Implementer codes, Reviewer audits existing output).