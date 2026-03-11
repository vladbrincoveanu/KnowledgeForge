# Context Level Execution Plan

## Purpose

This document turns the current Context Level discussion into an execution-ready plan that parallel boards can pick up without further interpretation.

Primary outcome:
- deliver a reliable C4 Level 1 extraction pipeline for system context
- keep deterministic extraction as the default path
- use LLMs for bounded adjudication, not primary extraction
- require human review for low-confidence or high-impact ambiguous cases

## Scope

In scope:
- context-level field extraction
- external dependency detection and classification
- LLM-assisted adjudication
- human-in-the-loop review flow
- field provenance, confidence, and evidence tracking
- validation corpus, scoring, and release gating

Out of scope:
- container-level extraction redesign
- component-level extraction redesign
- full UI design for review workflows

## Operating Principles

1. Deterministic first
Every field starts with code-based evidence collection and rule-based resolution.

2. LLM second
LLMs resolve ambiguity, classify unresolved candidates, and enrich explanations. They do not replace evidence collection.

3. Human third
If evidence conflicts or model confidence is below threshold, the result must be reviewable by a human.

4. Provenance always
Every field value must include source, confidence, evidence, and decision mode.

5. High-risk errors escalate
If a wrong value changes the system boundary, compliance posture, or ownership, the item must be reviewable.

## Shared Decision Contract

All context fields should converge on a common extraction result shape:

```json
{
  "value": "Stripe",
  "confidence": 0.97,
  "detection_source": "provider_catalog",
  "decision_mode": "deterministic",
  "review_status": "auto_accepted",
  "evidence": [
    {
      "type": "package_reference",
      "source": "requirements.txt",
      "snippet": "stripe==11.1.0"
    }
  ]
}
```

Required fields:
- `value`
- `confidence`
- `detection_source`
- `decision_mode` = `deterministic | llm_adjudicated | human_reviewed`
- `review_status` = `auto_accepted | needs_review | approved | rejected`
- `evidence[]`

## LLM Decision Policy

Use LLMs only after deterministic evidence collection.

Thresholds:
- `>= 0.90`: auto-accept
- `0.70 - 0.89`: accept with warning or secondary rule check
- `< 0.70`: send to review

The LLM must return strict JSON with:
- `classification`
- `confidence`
- `reasoning`
- `needs_review`
- `candidate_value`

## Competency Questions

These questions should be reused in prompts, tests, and reviewer checklists.

### External Dependencies
- Is this dependency outside the system boundary?
- Is it an external business system at C4 Level 1 or technical infrastructure for Level 2?
- Which real provider or company owns it?
- Is the evidence direct or inferred?
- Would a wrong classification alter the context diagram?

### Owner / Team
- Is ownership explicitly declared?
- Is the result derived from code ownership, commit history, CI metadata, or inference?
- Is the inferred owner recent and credible?

### Business Domain
- Does the service fit a fixed taxonomy category?
- Is the category supported by repo evidence or only inferred from naming?

### Actors
- Is the actor a human, internal service, or external system?
- Is the actor evidenced by auth config, API surface, or only README text?

## Delivery Model

Use six execution boards. Boards may run in parallel only where dependencies allow it.

## Three-Agent Parallel Execution Split

This section translates the board model into a practical three-agent setup.

Design principle:
- Agent 1 gets the highest-risk, most integrative work
- Agent 2 gets bounded metadata extraction work
- Agent 3 gets bounded runtime and platform-signal work

This minimizes merge conflicts and keeps the hardest architectural decisions with one owner.

### Agent 1: Lead Integration Lane

Role:
- primary architecture owner
- fastest lane
- owns cross-cutting contracts, dependency intelligence, LLM policy, and final integration

Owns:
- Board 0 entirely
- Board 1 entirely
- Board 5 entirely
- final integration points from Boards 2 to 4

Primary files and areas:
- `sources/Api/app/services/c4/context/context_manager.py`
- `sources/Api/app/services/c4/context/dependency_detector.py`
- `sources/Api/app/services/c4/context/dependency_classifier.py`
- new shared schema and review-queue modules
- validation harness and release docs

Tasks:
1. Define the shared extraction result contract.
2. Define the review queue contract.
3. Build the validation corpus and scorer.
4. Build the external provider catalog with at least 200 mappings.
5. Refactor dependency extraction into:
   - evidence collection
   - deterministic resolution
   - LLM adjudication
   - review queue emission
6. Add provenance and confidence to dependency output.
7. Build inter-service communication only where it directly reuses dependency evidence collectors.
8. Own weighted compliance score integration because it depends on outputs from both Agent 2 and Agent 3.
9. Own final merge of Agent 2 and Agent 3 outputs into the context pipeline.
10. Own final integration tests, migration notes, and release gate.

Why Agent 1 owns this:
- this lane has the highest architectural risk
- it defines the contracts the other two agents must build against
- it is the most likely place for hidden coupling and design mistakes

### Agent 2: Metadata Lane

Role:
- bounded field modernization
- primarily deterministic extraction with optional constrained LLM classification

Owns:
- Board 3 entirely
- metadata-related tests for those fields

Primary files and areas:
- `sources/Api/app/services/c4/context/metadata_detector.py`
- optional new helper modules for ownership, taxonomy, lifecycle, and bus factor

Tasks:
1. Rebuild owner detection fallback chain:
   - CODEOWNERS
   - recent git contributor or blame signal
   - CI/CD config variables
   - `UNKNOWN`
2. Add owner `detection_source`, `confidence`, and evidence.
3. Replace free-text business domain inference with fixed taxonomy classification.
4. Use LLM classification only for unresolved taxonomy decisions.
5. Remap service status to:
   - ACTIVE
   - MAINTENANCE
   - DEPRECATED
   - ARCHIVED
6. Replace `active_experts` with `bus_factor`.
7. Add unit tests and corpus scoring hooks for all metadata fields.

Why Agent 2 owns this:
- the work is mostly isolated to metadata logic
- it has clear interfaces and lower merge risk
- it does not need to block on the full dependency pipeline once the shared schema is defined

### Agent 3: Runtime and Platform Lane

Role:
- bounded detection of runtime-facing and platform-facing signals

Owns:
- most of Board 2
- most of Board 4

Primary files and areas:
- `sources/Api/app/services/c4/context/system_detector.py`
- new modules for API surface, documentation quality, deployment target, and runtime evidence extraction

Tasks:
1. Build API surface type detection:
   - REST
   - GraphQL
   - gRPC
   - CLI
   - WebSocket
   - Event-Driven
2. Improve actor detection using auth config and OpenAPI security evidence.
3. Split languages and frameworks cleanly.
4. Add framework version extraction.
5. Add deployment target detection.
6. Add documentation quality scoring.
7. Improve system purpose evidence collection:
   - route handlers
   - entrypoints
   - CLI help
8. Add unit tests and scorer hooks for these fields.

Why Agent 3 owns this:
- these tasks are modular and mostly file-scoped
- they can progress in parallel with minimal dependency on the provider catalog
- they produce evidence that Agent 1 can later consume during final integration

### Explicit Non-Goals Per Agent

Agent 2 should not:
- redesign dependency extraction
- change shared schema contracts without Agent 1 approval

Agent 3 should not:
- redesign dependency classification
- own final compliance integration

Agent 1 should not:
- rewrite Agent 2 or Agent 3 modules unless integration requires it

### Merge Boundaries

To reduce conflicts, each agent should avoid editing the same primary file at the same time.

Preferred ownership:
- Agent 1:
  - `context_manager.py`
  - `dependency_detector.py`
  - `dependency_classifier.py`
  - shared schemas
- Agent 2:
  - `metadata_detector.py`
  - metadata helpers
- Agent 3:
  - `system_detector.py`
  - API surface and platform helpers

If a shared file must be touched:
- Agent 1 merges it last
- Agent 2 and Agent 3 expose their outputs through new helper modules first
- integration wiring into `context_manager.py` stays with Agent 1

### Parallel Execution Order

#### Wave A: Contract First

Agent 1:
- define shared result schema
- define review queue schema
- publish output contracts for dependencies, metadata fields, and platform fields

Agent 2:
- wait for the schema contract, then start owner and lifecycle work

Agent 3:
- wait for the schema contract, then start API surface and platform-signal work

Exit criteria:
- shared field result contract is frozen for the sprint

#### Wave B: Independent Module Delivery

Agent 1:
- provider catalog
- deterministic dependency evidence collectors
- LLM adjudication contract

Agent 2:
- owner fallback
- status remap
- domain taxonomy
- bus factor

Agent 3:
- API surface detection
- framework split and versions
- deployment target
- documentation quality

Exit criteria:
- each lane has passing unit tests for its own modules
- each lane emits the shared result shape

#### Wave C: Integration and Ambiguity Handling

Agent 1:
- integrate Agent 2 and Agent 3 outputs into `context_manager.py`
- connect review queue handling
- connect scorer and corpus evaluation

Agent 2:
- fix metadata edge cases discovered during integration

Agent 3:
- fix runtime and platform edge cases discovered during integration

Exit criteria:
- end-to-end context output is complete
- ambiguous items become review items instead of silent guesses

#### Wave D: Final Validation

Agent 1:
- final integration tests
- release report
- migration notes

Agent 2:
- metadata quality review and field docs input

Agent 3:
- platform and runtime field docs input

Exit criteria:
- release gates pass or waivers are explicit

### Task Allocation Summary

#### Agent 1 Must Own
- shared contracts
- provider catalog
- dependency intelligence
- LLM adjudication and thresholds
- human review queue
- weighted compliance score integration
- integration wiring
- final validation and release

#### Agent 2 Must Own
- owner detection
- business domain taxonomy
- lifecycle status
- bus factor

#### Agent 3 Must Own
- API surface type
- actors via auth evidence
- language and framework split
- framework versions
- deployment target
- documentation quality
- system purpose evidence collection

### Daily Coordination Rules

1. Agent 1 publishes contract changes first.
2. Agent 2 and Agent 3 should build new helper modules before requesting integration.
3. No agent should change another agent's primary module without explicit handoff.
4. All ambiguous extraction cases should be surfaced as fixtures for the shared corpus.
5. Agent 1 is the final reviewer for cross-cutting design changes.

### Board 0: Program Foundation

Mission:
- define the shared schemas, scoring harness, and review contract

Tasks:
1. Define the canonical context field result schema.
2. Define the review item schema for ambiguous extractions.
3. Build a validation corpus with at least 20 representative repositories and ground truth.
4. Build an accuracy scorer for field-by-field evaluation.
5. Record baseline scores for all current context fields.
6. Define release gates for context-level changes.

Deliverables:
- schema document
- corpus manifest
- baseline report
- scoring script

Acceptance criteria:
- every context field can be evaluated with the same scorer contract
- baseline metrics are stored and reproducible
- a failed release gate blocks merge for material regressions

Dependencies:
- none

### Board 1: External Dependency Intelligence

Mission:
- make external dependency extraction the strongest and most auditable field in Context Level

Priority:
- highest

Tasks:
1. Create a provider catalog with at least 200 mappings.
2. Define the catalog schema:
   - package name or prefix
   - image name or prefix
   - env var patterns
   - URL patterns
   - Terraform or Helm indicators
   - provider label
   - company name
   - category
   - default context classification
3. Expand deterministic evidence collectors in `dependency_detector.py`:
   - manifests
   - import usage
   - env files
   - app settings
   - Dockerfiles
   - docker-compose
   - Helm values
   - Terraform
   - README and docs
4. Implement deterministic provider resolution from the catalog.
5. Implement conflict detection when evidence suggests multiple providers or mixed internal and external signals.
6. Refactor LLM use so it only adjudicates unresolved or conflicting candidates.
7. Create review items for low-confidence or high-impact ambiguous cases.
8. Add dependency provenance to output.
9. Add regression tests across Python, TypeScript, Java, Go, and .NET repos.

Deliverables:
- provider catalog file
- upgraded dependency detector
- LLM adjudication prompt and parser
- review queue output format
- accuracy report

Acceptance criteria:
- catalog contains at least 200 useful mappings
- deterministic path resolves at least 90% of dependency cases in the corpus
- ambiguous cases are emitted as reviewable items, not silently guessed
- every dependency includes evidence and confidence

Dependencies:
- Board 0

### Board 2: Runtime Relationships and Boundary Semantics

Mission:
- extract the real runtime edges that package-manager scanning misses

Tasks:
1. Add inter-service communication detection:
   - HTTP clients
   - gRPC clients
   - queue producers
   - queue consumers
   - event bus topics
   - webhook targets
2. Normalize outputs to:
   - target
   - protocol
   - direction
   - confidence
   - evidence
3. Add API surface type detection:
   - REST
   - GraphQL
   - gRPC
   - CLI
   - WebSocket
   - Event-Driven
4. Improve actor detection using:
   - auth config
   - OpenAPI security schemes
   - middleware
   - OAuth and API key patterns
5. Ensure actors and dependencies are distinguishable in the final context graph.

Deliverables:
- inter-service communication detector
- API surface detector
- actor enhancement logic

Acceptance criteria:
- runtime edges are emitted with protocol and direction
- actor detection accuracy materially improves over README-only extraction
- API surface detection reaches agreed accuracy threshold on corpus

Dependencies:
- Board 0
- Board 1 for reuse of dependency evidence patterns

### Board 3: Metadata Modernization

Mission:
- replace vague metadata with reviewable, high-signal context fields

Tasks:
1. Rebuild owner detection fallback chain:
   - CODEOWNERS
   - recent git blame or top contributor in last 90 days
   - CI/CD config variables
   - fallback to `UNKNOWN`
2. Add `detection_source` and `confidence` for ownership.
3. Replace free-text business domain inference with fixed taxonomy classification.
4. Use LLM classification only when rules and taxonomy hints are insufficient.
5. Remap service status to:
   - ACTIVE
   - MAINTENANCE
   - DEPRECATED
   - ARCHIVED
6. Replace `active_experts` with a bus factor score.
7. Keep the old field temporarily only if migration requires compatibility.

Deliverables:
- owner detection chain
- taxonomy-based business domain classifier
- lifecycle status mapper
- bus factor calculator

Acceptance criteria:
- owner blank rate falls below target
- business domain is chosen from a controlled taxonomy
- lifecycle statuses are explicit and deterministic
- bus factor output is documented and test-covered

Dependencies:
- Board 0

### Board 4: Platform and Quality Signals

Mission:
- strengthen fields that describe how the system is built, deployed, and documented

Tasks:
1. Split languages and frameworks cleanly.
2. Add framework version extraction.
3. Add deployment target detection:
   - Container
   - Kubernetes
   - Serverless
   - VM
   - Bare-Metal
   - PaaS
   - Unknown
4. Add documentation quality scoring.
5. Upgrade compliance scoring:
   - weighted numeric score
   - tier
   - evidence per check
   - configurable weights
6. Improve system purpose generation by feeding route handlers, entrypoints, and CLI help into the prompt instead of README only.

Deliverables:
- framework version extractor
- deployment target detector
- documentation quality scorer
- weighted compliance scorer
- improved purpose generator

Acceptance criteria:
- frameworks include versions where evidence exists
- compliance output is numeric plus tier plus breakdown
- documentation score is reproducible and explainable
- system purpose is materially better than README-first extraction

Dependencies:
- Board 0
- Board 2 for route and entrypoint evidence reuse

### Board 5: Validation, Review Workflow, and Release

Mission:
- make the new context pipeline safe to ship and maintain

Tasks:
1. Add integration tests for the full context pipeline.
2. Add migration handling for renamed or split fields.
3. Create field reference documentation.
4. Create configuration documentation for thresholds, weights, and taxonomy extension.
5. Define reviewer workflow for `needs_review` items.
6. Add before/after accuracy and coverage reports.
7. Gate release on:
   - no critical regression
   - review flow working
   - target metrics met or explicitly waived

Deliverables:
- integration test suite
- migration notes
- `FIELDS.md`
- `CONFIGURATION.md`
- release report

Acceptance criteria:
- context-level output is documented and testable
- ambiguous items are reviewable end-to-end
- release criteria are explicit and enforced

Dependencies:
- Boards 1 through 4

## Suggested Execution Order

Phase 1:
- Board 0
- Board 1

Phase 2:
- Board 2
- Board 3

Phase 3:
- Board 4

Phase 4:
- Board 5

## Work Items by Priority

### P0
- Board 0 Task 1 to 6
- Board 1 Task 1 to 6

### P1
- Board 1 Task 7 to 9
- Board 2 Task 1 to 3
- Board 3 Task 1 to 5

### P2
- Board 2 Task 4 to 5
- Board 3 Task 6 to 7
- Board 4 Task 1 to 5

### P3
- Board 4 Task 6
- Board 5 Task 1 to 7

## Data Model Changes

Required changes:
- add common decision metadata to all context fields
- rename `active_experts` to `bus_factor`
- split `languages` and `frameworks`
- add `api_surface_type`
- add `inter_service_comms`
- add `documentation_quality`
- add `deployment_target`
- upgrade `compliance` from tier-only to numeric plus tier plus breakdown

## Review Queue Definition

Create a machine-readable review queue item:

```json
{
  "field": "external_dependencies",
  "candidate_value": "Unknown SDK",
  "confidence": 0.58,
  "reason": "Package matched no catalog entry and URL evidence conflicts with internal hostname",
  "repo_path": "/repos/sample-service",
  "evidence": [
    {
      "type": "package_reference",
      "source": "requirements.txt",
      "snippet": "vendor-sdk==1.2.0"
    },
    {
      "type": "config_url",
      "source": "appsettings.json",
      "snippet": "https://gateway.internal.example/api"
    }
  ],
  "recommended_action": "human_review"
}
```

## Success Metrics

Minimum targets:
- deterministic external dependency resolution covers at least 90% of corpus cases
- owner blank rate is below 10%
- API surface detection accuracy is at least 85%
- business domain agreement with human labels is at least 80%
- inter-service communication detection improves runtime-edge coverage by at least 2x over package-manager-only detection
- documentation and compliance outputs are reproducible and explainable

## Risks

1. Overusing LLMs
Risk:
- higher cost, lower predictability, weaker auditability
Mitigation:
- allow LLM use only after deterministic collection and bounded prompts

2. False positives in dependency and comms detection
Risk:
- tests, dead code, and examples create fake edges
Mitigation:
- require multiple evidence signals and exclude test fixtures

3. Catalog maintenance burden
Risk:
- provider catalog goes stale
Mitigation:
- version the catalog and add contribution guidelines plus validation tests

4. Review queue overload
Risk:
- too many low-confidence items block progress
Mitigation:
- improve catalog coverage first and tune thresholds with corpus results

## Definition of Done

This plan is complete only when:
- the context pipeline emits decision metadata for each target field
- external dependency extraction is deterministic-first, LLM-second, human-third
- review items exist for ambiguous results
- field behavior is measured on a representative corpus
- docs, tests, and release gates are in place

## Immediate Next Step

Start with Board 0 and Board 1.

Reason:
- external dependency extraction is the current highest-value problem
- the shared schema and review contract must exist before other boards can build on them
