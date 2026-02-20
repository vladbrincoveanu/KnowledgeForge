## Why

KnowledgeForge needs a reliable way to transform fragmented repository knowledge
into a shared architectural understanding that both engineering and business teams
can trust. Building this now enables scalable onboarding, clearer ownership, and
faster architecture governance starting with the WPS system.

## What Changes

- Build ingestion and enrichment flows that harvest rich metadata from
  service-universe YAML and adjacent repository artifacts.
- Introduce automated generation of C4 Level-1 Context diagrams per software
  system, with WPS as the first supported system.
- Add a business-friendly context view that summarizes domain, ownership,
  lifecycle, tier, data class, experts, and compliance signals.
- Provide an interactive UI workflow for subject-matter experts to validate and
  augment generated context information.
- Establish a repeatable end-to-end pipeline from metadata extraction to
  diagram/context publishing.

## Capabilities

### New Capabilities

- `service-metadata-harvesting`: Extract and normalize high-value metadata from
  service-universe YAML and repository-adjacent artifacts into a unified context
  model.
- `c4-level1-context-generation`: Automatically generate accurate C4 Level-1
  context diagrams per system from harvested metadata, starting with WPS.
- `business-context-validation-ui`: Present concise business-facing context
  summaries and enable SME validation/augmentation in an interactive interface.

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `sources/Api/app/services/c4/context/` for metadata extraction, model
    enrichment, and context assembly.
  - `sources/Api` API endpoints supporting context retrieval, validation, and
    persistence of expert augmentations.
  - `sources/UI/src/` views/components for business summaries and expert review.
  - `sources/e2e/` to validate end-to-end extraction-to-UI workflows.
- Affected systems: API service, UI service, storage/backing metadata sources,
  and C4 rendering pipeline.
- Dependencies: service-universe YAML availability/quality, repository artifact
  parsers, and metadata completeness rules for ownership/compliance fields.
